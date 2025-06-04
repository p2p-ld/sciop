"""
These are *not quite unit tests* of pagination
since they use `/datasets` rather than some abstract pagination template page.

But they should do the trick...

At the time of writing, these are all static tests, not playwright tests.
Just the appearance and rendering logic is tested.

See also `tests/test_frontend/test_search.py` as pagination and search are linked systems.
"""

import string
from itertools import cycle
from math import ceil
from typing import Callable as C
from typing import Literal

from bs4 import BeautifulSoup
from httpx import Response
from starlette.testclient import TestClient

from sciop.models import Dataset

ITEMS_PER_PAGE = 1


def _make_items(n: int, dataset: C[..., Dataset]) -> list[Dataset]:
    """Make items for different numbers of pages"""
    datasets = []
    letters = cycle(string.ascii_lowercase)
    for i in range(n):
        letter = next(letters)
        letter = letter * max((ceil(((i + 1) / len(string.ascii_lowercase))) + 1), 2)

        ds = dataset(slug=letter, tags=["default"])
        datasets.append(ds)
    return datasets


def _get_pagination_links(page: Response) -> BeautifulSoup | None:
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "lxml")
    # just get the first one, bottom should be identical
    pagination_links = soup.select_one("div.pagination-links")
    if pagination_links is None:
        return None
    return pagination_links


def _get_page_numbers(links: BeautifulSoup) -> list[str]:
    page_links = links.select(".page-link")
    assert len(page_links) == 5
    pages = [page.text.strip() for page in page_links]
    return pages


def _assert_arrows_disabled(
    links: BeautifulSoup, which: Literal["first", "last"] = "first"
) -> None:
    if which == "first":
        first: BeautifulSoup = links.select_one(".first-link")
        assert "disabled" in first.attrs
        prev: BeautifulSoup = links.select_one(".back-link")
        assert "disabled" in prev.attrs
    elif which == "last":
        last: BeautifulSoup = links.select_one(".end-link")
        assert "disabled" in last.attrs
        next: BeautifulSoup = links.select_one(".forward-link")
        assert "disabled" in next.attrs
    else:
        raise ValueError()


def test_lt1_page(client: TestClient, dataset, set_config):
    """
    When we have <1 page worth of items, no pagination shown.
    """
    set_config(enable_versions=False)
    _make_items(n=1, dataset=dataset)
    res = client.get("/datasets/search/", headers={"HX-Request": "true"})
    links = _get_pagination_links(res)
    assert links is None


def test_lt5_pages(client, dataset, set_config):
    """
    Test pagination with less than 5 pages -
    should just be normal...
    """
    set_config(enable_versions=False)
    _make_items(n=ITEMS_PER_PAGE * 4, dataset=dataset)
    res = client.get("/datasets/search/?size=1", headers={"HX-Request": "true"})
    links = _get_pagination_links(res)
    assert len(links.select(".pagination-link")) == 8
    _assert_arrows_disabled(links)
    res = client.get("/datasets/search/?page=4&size=1", headers={"HX-Request": "true"})
    links = _get_pagination_links(res)
    assert len(links.select(".pagination-link")) == 8
    _assert_arrows_disabled(links, "last")


def test_5_pages(client: TestClient, dataset, set_config):
    """
    When we have exactly 5 pages, make sure we don't render 0th page

    References:
        https://codeberg.org/Safeguarding/sciop/pulls/433
    """
    set_config(enable_versions=False)
    _make_items(
        n=5 * ITEMS_PER_PAGE,
        dataset=dataset,
    )
    res = client.get("/datasets/search/?page=3&size=1", headers={"HX-Request": "true"})
    links = _get_pagination_links(res)
    assert len(links.select(".pagination-link")) == 9
    assert _get_page_numbers(links) == ["1", "2", "3", "4", "5"]


def test_gt5_pages(client: TestClient, dataset, set_config):
    """
    When we have more than 5 pages, we should add ellipses to indicate pages are omitted
    """
    set_config(enable_versions=False)
    _make_items(
        n=7 * ITEMS_PER_PAGE,
        dataset=dataset,
    )
    res = client.get("/datasets/search/?size=1", headers={"HX-Request": "true"})
    links = _get_pagination_links(res)
    assert len(links.select(".pagination-link")) == 9
    _assert_arrows_disabled(links)
    assert _get_page_numbers(links) == ["1", "2", "3", "4", "5"]
    soup = BeautifulSoup(res.text, "lxml")
    assert len(soup.select_one(".pagination-links").select(".pagination-ellipses")) == 1

    # last button takes us to the last page
    assert "page=7" in links.select_one(".end-link").attrs["hx-get"]

    res = client.get("/datasets/search/?page=4&size=1", headers={"HX-Request": "true"})
    links = _get_pagination_links(res)
    assert _get_page_numbers(links) == ["2", "3", "4", "5", "6"]
    soup = BeautifulSoup(res.text, "lxml")
    assert len(soup.select_one(".pagination-links").select(".pagination-ellipses")) == 2

    res = client.get("/datasets/search/?page=7&size=1", headers={"HX-Request": "true"})
    links = _get_pagination_links(res)
    assert _get_page_numbers(links) == ["3", "4", "5", "6", "7"]
    _assert_arrows_disabled(links, "last")
