import pytest

from sciop.config import config
from sciop.models import Scopes


@pytest.mark.parametrize("scope", Scopes.__members__.values())
@pytest.mark.parametrize("header_type", ["admin_auth_header", "root_auth_header"])
def test_account_scope_grant(scope: Scopes, client, account, session, header_type, request):
    auth_header = request.getfixturevalue(header_type)
    account_ = account(username="scoped")
    response = client.put(
        config.api_prefix + f"/accounts/{account_.username}/scopes/{scope.value}",
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
        config.api_prefix + "/accounts/admin/scopes/admin",
        headers=admin_auth_header,
    )
    assert response.status_code == 403
    assert "Only root can change admin" in response.text


def test_self_revoke_root(client, root_auth_header):
    """
    Root accounts can't revoke their own admin scope
    """
    response = client.delete(
        config.api_prefix + "/accounts/root/scopes/root",
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
            config.api_prefix + f"/accounts/receiving/scopes/{privileged_scope}",
            headers=auth_header,
        )
    elif method == "delete":
        receiving_account_ = account(scopes=[privileged_scope], username="receiving")
        response = client.delete(
            config.api_prefix + f"/accounts/receiving/scopes/{privileged_scope}",
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
    response = client.delete(
        config.api_prefix + "/accounts/admin",
        headers=admin_auth_header,
    )
    assert response.status_code == 403
    assert "cannot suspend yourself" in response.text


@pytest.mark.parametrize("account_type", ("admin", "root"))
def test_no_admin_suspend(client, account, get_auth_header, account_type, admin_user, root_user):
    account_ = account(scopes=["admin"], username="new_admin", password="passywordy123")
    auth_header = get_auth_header(username="new_admin", password="passywordy123")
    response = client.delete(
        config.api_prefix + f"/accounts/{account_type}",
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
        config.api_prefix + f"/accounts/{account_.username}/scopes/review",
        headers=admin_auth_header,
    )
    assert response.status_code == 200

    session.refresh(account_)
    assert account_.has_scope("review")
    assert len(account_.scopes) == 1

    response = client.put(
        config.api_prefix + f"/accounts/{account_.username}/scopes/review",
        headers=admin_auth_header,
    )
    assert response.status_code == 200
    session.refresh(account_)
    assert account_.has_scope("review")
    assert len(account_.scopes) == 1


@pytest.mark.skip()
def test_deny_dataset_no_delete():
    pass


@pytest.mark.skip()
def test_deny_dataset_part_no_delete():
    pass


@pytest.mark.skip()
def test_suspend_account_no_delete():
    pass
