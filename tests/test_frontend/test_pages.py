import pytest


@pytest.mark.parametrize("url", ("/", "/datasets", "/docs", "/feeds", "/uploads"))
def test_public_pages_load(url, client_lifespan):
    """
    The babiest of tests, just make sure public pages load.

    Remove this once we have proper tests for pages
    """
    response = client_lifespan.get(url)
    assert response.status_code == 200


@pytest.mark.parametrize("url", ("/request", "/self", "/self/review", "/self/admin", "/self/log"))
def test_admin_pages_load(url, client, admin_auth_header):
    """
    More of the babiest of tests, just make sure admin pages load.

    Remove this once we have proper tests for pages
    """
    response = client.get(url, headers=admin_auth_header)
    assert response.status_code == 200
