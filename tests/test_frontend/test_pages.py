import pytest
from bs4 import BeautifulSoup as bs
from starlette.testclient import TestClient

LOGGED_OUT_PAGES = ("/", "/datasets/", "/feeds", "/uploads/", "/login")
LOGGED_IN_PAGES = ("/self/",)
REVIEW_PAGES = ("/self/review",)
ADMIN_PAGES = ("/self/admin", "/self/log")

# note that we specifically don't include /docs here.
# that requires the lifespan methods to run, so is more expensive,
# and all we want to do is check that it loads here.
ALL_PAGES = LOGGED_OUT_PAGES + LOGGED_IN_PAGES + REVIEW_PAGES + ADMIN_PAGES
SCOPED_PAGES = REVIEW_PAGES + ADMIN_PAGES
NONPUBLIC_PAGES = tuple(set(ALL_PAGES) - set(LOGGED_OUT_PAGES))


@pytest.mark.parametrize("url", LOGGED_OUT_PAGES)
def test_public_pages_load(url, client: TestClient):
    """
    The babiest of tests, just make sure public pages load.

    Remove this once we have proper tests for pages
    """
    response = client.get(url)
    assert response.status_code == 200
    assert response.url.path == url


@pytest.mark.parametrize("url", NONPUBLIC_PAGES)
def test_nonpublic_pages_dont_load(url, client):
    """When we are logged out, we should not be able to see any nonpublic pages"""
    response = client.get(url)
    # either we are not shown the page or we were redirected to a public page
    assert response.status_code != 200 or str(response.url) not in NONPUBLIC_PAGES


@pytest.mark.parametrize("url", ALL_PAGES)
def test_admin_pages_load(url, client: TestClient, admin_auth_header):
    """
    More of the babiest of tests,
    just the absolute minimum of what should be true for all pages while logged in

    Remove this once we have proper tests for pages
    """
    response = client.get(url, headers=admin_auth_header)
    assert response.status_code == 200
    if url == "/login":
        assert response.url.path == "/self/"
    else:
        assert response.url.path == url

    # we should be shown as logged in on all pages
    soup = bs(response.content, "html.parser")
    account = soup.select_one(".account-button")
    assert account.text == "admin"


def test_docs_load(client_lifespan):
    """
    Just make sure we don't trivially break the docs while they're still in-repo
    """
    response = client_lifespan.get("/docs")
    assert response.status_code == 200
