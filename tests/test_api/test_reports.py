import pytest
from starlette.testclient import TestClient

from sciop.config import get_config
from sciop.models import ReportType


@pytest.mark.parametrize("report_type", ReportType.__members__.keys())
def test_report_item(
    client: TestClient,
    account,
    get_auth_header,
    reportable_item,
    report_type: str,
    request: pytest.FixtureRequest,
):
    """
    Anyone can create a report!

    Tests that all the report types are allowed for all object types
    and there isn't any wonky behavior in the base behavior
    """
    acct = account()
    header = get_auth_header(acct.username)
    comment = "my thing to say"
    expected = {
        "target_type": reportable_item.__name__.replace(" ", "_"),
        "target": reportable_item.short_name,
        "report_type": report_type,
        "comment": comment,
    }
    res = client.post(f"{get_config().api_prefix}/reports/", json=expected, headers=header)
    assert res.status_code == 200
    created = res.json()
    for k, v in expected.items():
        if k == "target":
            continue
        assert created[k] == v
    # just make sure that we are returned a target object rather than its name
    assert isinstance(created["target"], dict)


def test_reporting_requires_login(dataset, client):
    ds = dataset()
    expected = {
        "target_type": "dataset",
        "target": ds.slug,
        "report_type": "rules",
        "comment": "",
    }
    res = client.post(f"{get_config().api_prefix}/reports/", json=expected)
    assert res.status_code == 401


@pytest.mark.parametrize("reportable_item", ["dataset"], indirect=True)
def test_report_visibility(
    resolving_account, reporting_account, reported_item, client, get_auth_header
) -> None:
    """
    Reports can be viewed by
    - opening account
    - reviewers

    and can't be viewed by
    - anonymous requests
    - other non-scoped accounts
    """
    ds, report = reported_item

    # report is not visible to unauthorized gets/posts always
    res = client.get(report.api_url)
    assert res.status_code == 401
    res = client.post(report.api_url + "/resolve", json={"action": "dismiss"})
    assert res.status_code == 401

    header = get_auth_header(resolving_account.username)
    res = client.get(report.api_url, headers=header)
    report_list = client.get(get_config().api_prefix + "/reports", headers=header)

    if resolving_account.username in ("admin", "reviewer", "reporter"):
        assert res.status_code == 200
        assert report_list.status_code == 200
        assert len(report_list.json()["items"]) > 0
    else:
        assert res.status_code == 403
        assert report_list.status_code == 200
        assert len(report_list.json()["items"]) == 0


def test_resolve_dismiss(reported_item, resolving_account, get_auth_header, client, session):
    """Dismissing does nothing!"""
    header = get_auth_header(resolving_account.username)
    item, report = reported_item
    session.refresh(item)
    dumped = item.model_dump()
    data = {"action": "dismiss"}

    res = client.post(report.api_url + "/resolve", json=data, headers=header)

    session.refresh(item)
    refreshed = item.model_dump()
    if resolving_account.username not in ("admin", "reviewer"):
        assert res.status_code == 403
    else:
        assert res.status_code == 200
        assert res.json()["action"] == "dismiss"

    assert dumped == refreshed


def test_resolve_hide(reported_item, resolving_account, get_auth_header, client, session):
    """Hiding an item removes its approval status and makes it invisible"""
    header = get_auth_header(resolving_account.username)
    item, report = reported_item
    session.refresh(item)
    dumped = item.model_dump()
    data = {"action": "hide"}

    res = client.post(report.api_url + "/resolve", json=data, headers=header)

    session.refresh(item)
    refreshed = item.model_dump()
    if resolving_account.username not in ("admin", "reviewer"):
        assert res.status_code == 403
        assert dumped == refreshed
    elif report.target_type == "account":
        assert res.status_code == 422
        assert dumped == refreshed
    else:
        assert res.status_code == 200
        assert res.json()["action"] == "hide"
        assert dumped["is_approved"]
        assert not refreshed["is_approved"]


def test_resolve_remove(reported_item, resolving_account, get_auth_header, client, session):
    """
    Removing an item renders it effectively deleted
    """
    header = get_auth_header(resolving_account.username)
    item, report = reported_item
    session.refresh(item)
    dumped = item.model_dump()
    data = {"action": "remove"}
    assert client.get(item.frontend_url).status_code == 200

    res = client.post(report.api_url + "/resolve", json=data, headers=header)

    session.refresh(item)
    refreshed = item.model_dump()
    if resolving_account.username not in ("admin", "reviewer"):
        assert res.status_code == 403
        assert dumped == refreshed
    elif report.target_type == "account":
        assert res.status_code == 422
        assert dumped == refreshed
    else:
        assert res.status_code == 200
        assert res.json()["action"] == "remove"
        assert not dumped["is_removed"]
        assert refreshed["is_removed"]
        assert client.get(item.frontend_url).status_code == 404


def test_resolve_suspend(
    reported_item, resolving_account, get_auth_header, client, session, reported_account, dataset
):
    """
    Suspends the reported account or the account that created the reported item,
    removing the item but NOT any other items created by the suspended account
    """
    extra = dataset(slug="extra", account_=reported_account, is_approved=True)

    header = get_auth_header(resolving_account.username)
    item, report = reported_item
    session.refresh(item)
    dumped = item.model_dump()
    data = {"action": "suspend"}

    res = client.post(report.api_url + "/resolve", json=data, headers=header)

    session.refresh(item)
    session.refresh(extra)
    refreshed = item.model_dump()

    assert not extra.is_removed
    if resolving_account.username not in ("admin",):
        assert res.status_code == 403
        assert dumped == refreshed
        assert not report.reported_account.is_suspended
    else:
        assert res.status_code == 200
        assert res.json()["action"] == "suspend"
        assert report.reported_account.is_suspended

        if report.target_type != "account":
            assert not dumped["is_removed"]
            assert refreshed["is_removed"]
        assert client.get(item.frontend_url).status_code == 404


def test_resolve_suspend_remove(
    reported_item, resolving_account, get_auth_header, client, session, reported_account, dataset
):
    """
    Suspends the reported account or the account that created the reported item
    and removes all items
    """
    extra = dataset(slug="extra", account_=reported_account, is_approved=True)

    header = get_auth_header(resolving_account.username)
    item, report = reported_item
    session.refresh(item)
    dumped = item.model_dump()
    data = {"action": "suspend_remove"}

    res = client.post(report.api_url + "/resolve", json=data, headers=header)

    session.refresh(item)
    session.refresh(extra)
    refreshed = item.model_dump()

    if resolving_account.username not in ("admin",):
        assert res.status_code == 403
        assert dumped == refreshed
        assert not extra.is_removed
        assert not report.reported_account.is_suspended
    else:
        assert res.status_code == 200
        assert res.json()["action"] == "suspend_remove"
        assert report.reported_account.is_suspended
        assert extra.is_removed
        if report.target_type != "account":
            assert not dumped["is_removed"]
            assert refreshed["is_removed"]
        assert client.get(item.frontend_url).status_code == 404
