import pytest
from bs4 import BeautifulSoup

TEST_PAGES = ("/", "/datasets", "/datasets/default", "/uploads/defaultt")


@pytest.mark.parametrize("page", TEST_PAGES)
def test_has_h1(client, page, default_db):
    """
    Pages should all have an h1 at the top of the page
    """
    result = client.get(page)
    soup = BeautifulSoup(result.content, "lxml")
    container = soup.find("div", {"class": "container"})
    flat_nodes = container.find_all(True)
    assert [elt.name == "h1" for elt in flat_nodes[0:5]]
