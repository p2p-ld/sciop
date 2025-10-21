import pytest
from starlette.testclient import TestClient

from sciop.models import Account, Dataset, DatasetPart, Report, ReportType, Upload


@pytest.fixture(params=["account", "dataset", "dataset_part", "upload"])
def reportable_item(
    request: pytest.FixtureRequest, account, dataset, dataset_part, upload
) -> Account | Dataset | DatasetPart | Upload:
    """
    An item that is to be reported
    """
    acct = account(username="reporty")
    if request.param == "account":
        return acct
    elif request.param == "dataset":
        return dataset(slug="reported", account_=acct)
    elif request.param == "dataset_part":
        return dataset_part(part_slug="reported", account_=acct)
    elif request.param == "upload":
        return upload(account_=acct)


@pytest.fixture
def reported_item(
    reportable_item, session, account
) -> tuple[Account | Dataset | DatasetPart | Upload, Report]:
    """
    An item that is reported and its associated report
    """
    acct = account(username="reporter")
    if isinstance(reportable_item, Account):
        kwargs = {"target_account": reportable_item}
    elif isinstance(reportable_item, Dataset):
        kwargs = {"target_dataset": reportable_item}
    elif isinstance(reportable_item, DatasetPart):
        kwargs = {"target_dataset_part": reportable_item}
    elif isinstance(reportable_item, Upload):
        kwargs = {"target_upload": reportable_item}
    else:
        raise ValueError(f"Unknown item type: {reportable_item}")
    report = Report(opened_by=acct, **kwargs)
    session.add(report)
    session.commit()
    session.refresh(report)
    return reportable_item, report


@pytest.fixture(params=["admin", "reviewer", "rando"])
def resolving_account(request: pytest.FixtureRequest, account) -> Account:
    """
    Account attempting to resolve report, with varying permissions levels
    """
    if request.param == "admin":
        acct = account(username=request.param, scopes=["admin"])
    elif request.param == "reviewer":
        acct = account(username=request.param, scopes=["review"])
    elif request.param == "rando":
        acct = account(username=request.param)
    else:
        raise ValueError()
    return acct


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
        "target_type": request.param,
        "target": reportable_item.short_name,
        "report_type": report_type,
        "comment": comment,
    }
    res = client.post("/reports/", json=expected, headers=header)
    assert res.status_code == 200
    created = res.json()
    for k, v in expected.items():
        assert created[k] == v


@pytest.mark.xfail()
def test_reporting_requires_login():
    raise NotImplementedError()


@pytest.mark.xfail()
def test_report_visibility():
    """
    Reports can be viewed by
    - opening account
    - reviewers

    and can't be viewed by
    - anonymous requests
    - other non-scoped accounts
    """
    raise NotImplementedError()


@pytest.mark.xfail
def test_resolve_dismiss():
    """Dismissing does nothing!"""
    raise NotImplementedError()


@pytest.mark.xfail
def test_resolve_hide():
    """Hiding an item removes its approval status and makes it invisible"""
    raise NotImplementedError()


@pytest.mark.xfail
def test_resolve_remove():
    """
    Removing an item renders it effectively deleted
    """
    raise NotImplementedError()


@pytest.mark.xfail
def test_resolve_suspend():
    """
    Suspends the reported account or the account that created the reported item
    """
    raise NotImplementedError()


@pytest.mark.xfail
def test_resolve_suspend_remove():
    """
    Suspends the reported account or the account that created the reported item
    and removes all items
    """
    raise NotImplementedError()


@pytest.mark.xfail
def test_unauthorized_cant_resolve():
    """
    Unauthorized users can't resolve
    """
    raise NotImplementedError()


@pytest.mark.xfail
def test_review_cant_suspend():
    """
    An account with review but not admin permissions can't suspend accounts
    """
    raise NotImplementedError()
