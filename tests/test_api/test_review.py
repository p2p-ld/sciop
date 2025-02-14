import pytest

from sciop.config import config
from sciop.models import Scopes


@pytest.mark.parametrize("scope", Scopes.__members__.values())
def test_account_scope_grant(scope: Scopes, client, account, session, admin_auth_header):
    response = client.put(
        config.api_prefix + f"/accounts/{account.username}/scopes/{scope.value}",
        headers=admin_auth_header,
    )
    assert response.status_code == 200

    session.refresh(account)
    assert account.has_scope(scope.value)
