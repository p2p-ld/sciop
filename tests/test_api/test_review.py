import pytest
from sqlmodel import select

from sciop.config import get_config
from sciop.models import AuditLog, DatasetPart
from sciop.types import Scopes


@pytest.mark.parametrize("scope", Scopes.__members__.values())
@pytest.mark.parametrize("header_type", ["admin_auth_header", "root_auth_header"])
def test_account_scope_grant(scope: Scopes, client, account, session, header_type, request):
    auth_header = request.getfixturevalue(header_type)
    account_ = account(username="scoped")
    response = client.put(
        get_config().api_prefix + f"/accounts/{account_.username}/scopes/{scope.value}",
        headers=auth_header,
    )
    if scope not in (Scopes.admin, Scopes.root) or header_type == "root_auth_header":
        assert response.status_code == 200
        session.refresh(account_)
        assert account_.has_scope(scope.value)
    else:
        assert response.status_code == 403
        session.refresh(account_)
        assert not account_.has_scope(scope.value)


def test_self_revoke_admin(client, admin_auth_header):
    """
    Admin accounts can't revoke their own admin scope
    """
    response = client.delete(
        get_config().api_prefix + "/accounts/admin/scopes/admin",
        headers=admin_auth_header,
    )
    assert response.status_code == 403
    assert "Only root can change admin" in response.text


def test_self_revoke_root(client, root_auth_header):
    """
    Root accounts can't revoke their own admin scope
    """
    response = client.delete(
        get_config().api_prefix + "/accounts/root/scopes/root",
        headers=root_auth_header,
    )
    assert response.status_code == 403
    assert "remove root scope from yourself" in response.text.lower()


@pytest.mark.parametrize("method", ["put", "delete"])
@pytest.mark.parametrize("granting_scope", Scopes.__members__.values())
@pytest.mark.parametrize("privileged_scope", ["admin", "root"])
def test_only_root_can_privilege(
    method, granting_scope, privileged_scope, client, account, get_auth_header, session
):
    """
    Only root can assign or unassign admin and root scopes

    We allow ourselves to be a little wasteful here and test against all the granting scopes
    even if it's only `admin` we care about because this is critical behavior.
    """
    granting_account_ = account(
        scopes=[granting_scope], username="granting", password="granting12345"
    )
    auth_header = get_auth_header(username="granting", password="granting12345")
    if method == "put":
        receiving_account_ = account(username="receiving")
        response = client.put(
            get_config().api_prefix + f"/accounts/receiving/scopes/{privileged_scope}",
            headers=auth_header,
        )
    elif method == "delete":
        receiving_account_ = account(scopes=[privileged_scope], username="receiving")
        response = client.delete(
            get_config().api_prefix + f"/accounts/receiving/scopes/{privileged_scope}",
            headers=auth_header,
        )
    else:
        raise ValueError("Unhandled method")

    session.refresh(receiving_account_)
    if granting_scope == Scopes.root:
        assert response.status_code == 200
        if method == "put":
            assert receiving_account_.has_scope(privileged_scope)
        elif method == "delete":
            assert not receiving_account_.has_scope(privileged_scope)
    else:
        assert response.status_code == 403
        assert "only root" in response.text.lower() or "must be admin" in response.text.lower()
        if method == "put":
            assert not receiving_account_.has_scope(privileged_scope)
        elif method == "delete":
            assert receiving_account_.has_scope(privileged_scope)


def test_self_suspend(client, admin_auth_header):
    """
    Accounts should not be able to suspend themselves
    """
    response = client.post(
        get_config().api_prefix + "/accounts/admin/suspend",
        headers=admin_auth_header,
    )
    assert response.status_code == 403
    assert "cannot suspend yourself" in response.text


@pytest.mark.parametrize("account_type", ("admin", "root"))
def test_no_admin_suspend(client, account, get_auth_header, account_type, admin_user, root_user):
    account_ = account(scopes=["admin"], username="new_admin", password="passywordy123")
    auth_header = get_auth_header(username="new_admin", password="passywordy123")
    response = client.post(
        get_config().api_prefix + f"/accounts/{account_type}/suspend",
        headers=auth_header,
    )
    assert response.status_code == 403
    assert "Admins can't can't ban other admins" in response.text


def test_no_double_scope(session, client, account, admin_auth_header):
    """
    A scope can't be assigned twice, and the grant scope method is idempotent
    """
    account_ = account(username="scoped")
    assert not account_.has_scope("review")
    assert len(account_.scopes) == 0
    response = client.put(
        get_config().api_prefix + f"/accounts/{account_.username}/scopes/review",
        headers=admin_auth_header,
    )
    assert response.status_code == 200

    session.refresh(account_)
    assert account_.has_scope("review")
    assert len(account_.scopes) == 1

    response = client.put(
        get_config().api_prefix + f"/accounts/{account_.username}/scopes/review",
        headers=admin_auth_header,
    )
    assert response.status_code == 200
    session.refresh(account_)
    assert account_.has_scope("review")
    assert len(account_.scopes) == 1


def test_deny_dataset_no_delete(client, dataset, session, admin_auth_header):
    ds_ = dataset(slug="unapproved", is_approved=False)
    res = client.post(
        f"{get_config().api_prefix}/datasets/{ds_.slug}/deny", headers=admin_auth_header
    )
    assert res.status_code == 200
    session.refresh(ds_)
    assert ds_.is_removed
    assert "REM" in ds_.slug
    log = session.exec(select(AuditLog)).first()
    assert log.target_dataset is ds_
    assert log.action == "deny"


def test_approve_dataset(client, dataset, session, admin_auth_header):
    ds_ = dataset(slug="unapproved", is_approved=False)
    assert not ds_.is_approved
    res = client.post(
        f"{get_config().api_prefix}/datasets/{ds_.slug}/approve", headers=admin_auth_header
    )
    assert res.status_code == 200
    session.refresh(ds_)
    assert ds_.is_approved


def test_unapprove_dataset(client, dataset, session, admin_auth_header):
    ds_ = dataset(slug="approved", is_approved=True)
    assert ds_.is_approved
    res = client.post(
        f"{get_config().api_prefix}/datasets/{ds_.slug}/unapprove", headers=admin_auth_header
    )
    assert res.status_code == 200
    session.refresh(ds_)
    assert not ds_.is_approved


def test_approve_upload(client, upload, session, admin_auth_header):
    ul_ = upload(is_approved=False)
    assert not ul_.is_approved
    res = client.post(
        f"{get_config().api_prefix}/uploads/{ul_.infohash}/approve", headers=admin_auth_header
    )
    assert res.status_code == 200
    session.refresh(ul_)
    assert ul_.is_approved


def test_unapprove_upload(client, upload, session, admin_auth_header):
    ul_ = upload(is_approved=True)
    assert ul_.is_approved
    res = client.post(
        f"{get_config().api_prefix}/uploads/{ul_.infohash}/unapprove", headers=admin_auth_header
    )
    assert res.status_code == 200
    session.refresh(ul_)
    assert not ul_.is_approved


def test_deny_dataset_part_no_delete(client, dataset, session, admin_auth_header):
    ds_ = dataset(slug="unapproved", is_approved=True)
    ds_.parts.append(DatasetPart(part_slug="unapproved-part"))
    session.add(ds_)
    session.commit()
    res = client.post(
        f"{get_config().api_prefix}/datasets/{ds_.slug}/unapproved-part/deny",
        headers=admin_auth_header,
    )
    assert res.status_code == 200
    session.refresh(ds_)
    part = ds_.parts[0]
    assert part.is_removed
    assert "REM" in part.part_slug
    log = session.exec(select(AuditLog)).first()
    assert log.target_dataset_part is part
    assert log.action == "deny"


def test_deny_upload_no_delete(client, upload, session, admin_auth_header):
    ul = upload(is_approved=False)
    res = client.post(
        f"{get_config().api_prefix}/uploads/{ul.infohash}/deny", headers=admin_auth_header
    )
    assert res.status_code == 200
    session.refresh(ul)
    assert ul.is_removed
    assert "REM" in ul.infohash
    log = session.exec(select(AuditLog)).first()
    assert log.target_upload is ul
    assert log.action == "deny"


def test_suspend_account_no_delete(client, account, session, admin_auth_header):
    acc = account()
    res = client.post(
        f"{get_config().api_prefix}/accounts/{acc.username}/suspend", headers=admin_auth_header
    )
    assert res.status_code == 200
    session.refresh(acc)
    assert acc.is_suspended
    log = session.exec(select(AuditLog)).first()
    assert log.target_account is acc
    assert log.action == "suspend"


def test_suspended_accounts_cant_unsuspend(
    client, account, session, root_auth_header, get_auth_header
):
    """Suspended accounts cant use stale tokens to give scopes or unban themselves"""

    acc = account(scopes=["admin"])
    smurf = account(username="smurf")
    acc_header = get_auth_header(username=acc.username)

    res = client.post(
        f"{get_config().api_prefix}/accounts/{acc.username}/suspend", headers=root_auth_header
    )
    assert res.status_code == 200
    session.refresh(acc)
    assert acc.is_suspended

    res = client.post(
        f"{get_config().api_prefix}/accounts/{acc.username}/restore", headers=acc_header
    )
    assert res.status_code == 403
    session.refresh(acc)
    assert acc.is_suspended

    res = client.put(f"{get_config().api_prefix}/accounts/smurf/scopes/review", headers=acc_header)
    assert res.status_code == 403
    session.refresh(smurf)
    assert not smurf.has_scope("review")
