import pytest
from bs4 import BeautifulSoup
import re

TEST_PAGES = (
    "/",
    "/datasets",
    "/datasets/default",
    "/uploads/defaultt",
    "/login",
    "/self",
    "/self/review",
    "/self/admin",
    "/self/log",
)


@pytest.mark.parametrize("page", TEST_PAGES)
def test_headers(client, page, default_db, admin_auth_header):
    """
    Pages should
    - all have an h1 at the top of the page
    - have no (positive) jumps in header levels

    TODO: These should probably be selenium tests but i am so tired
    """
    result = client.get(page, headers=admin_auth_header)
    assert result.status_code == 200
    soup = BeautifulSoup(result.content, "lxml")

    # First header is h1
    all_headers = soup.find_all(re.compile("^h[1-6]$"))
    assert all_headers[0].name == "h1"

    # headers don't have jumps
    if len(all_headers) > 1:
        header_levels = [int(head.name[-1]) for head in all_headers]
        diff = [header_levels[i] - header_levels[i - 1] for i in range(1, len(header_levels))]
        one_or_below = [d <= 1 for d in diff]
        assert all(one_or_below)
