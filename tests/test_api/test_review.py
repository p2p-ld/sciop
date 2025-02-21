import pytest

from sciop.config import config
from sciop.models import Scopes


@pytest.mark.parametrize("scope", Scopes.__members__.values())
def test_account_scope_grant(scope: Scopes, client, account, session, admin_auth_header):
    account_ = account(username="scoped")
    response = client.put(
        config.api_prefix + f"/accounts/{account_.username}/scopes/{scope.value}",
        headers=admin_auth_header,
    )
    assert response.status_code == 200

    session.refresh(account_)
    assert account_.has_scope(scope.value)


def test_self_revoke_admin(client, admin_auth_header):
    """
    Admin accounts can't revoke their own admin scope
    """
    response = client.delete(
        config.api_prefix + "/accounts/admin/scopes/admin",
        headers=admin_auth_header,
    )
    assert response.status_code == 403
    assert "cannot revoke admin" in response.text


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
