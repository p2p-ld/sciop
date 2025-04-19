import string
from math import floor

import pytest
from sqlmodel import Session


@pytest.fixture(scope="module")
def items(session_module: Session, dataset_module, upload_module, request: pytest.FixtureRequest):
    """The datasets we're gonna be searching and sorting"""
    dataset = dataset_module
    upload = upload_module

    ds = dataset(session_=session_module)
    uploads = []
    for i in range(100):
        letter = string.ascii_letters[i % 25]
        letter = letter * (floor(i / 25))
        ul = upload(session_=session_module, dataset_=ds, file_name=letter + ".torrent")
        uploads.append(ul)
    return uploads


@pytest.mark.skip(reason="TODO")
def test_search_base():
    """We can search and subset queries"""


def test_sort_base(items, page, run_server_module):
    """
    Basic sort behavior, we can sort by a single column
    :return:
    """
    pass


def test_sort_paging():
    """
    Sorting should work through paging
    """
    pass


@pytest.mark.skip(reason="TODO")
def test_sort_multicol():
    """
    We can sort multiple columns at the same time
    """


@pytest.mark.skip(reason="TODO")
def test_sort_multiparam():
    """
    We can sort as well as subset with a query and use pagination at the same time
    """


@pytest.mark.skip(reason="TODO")
@pytest.mark.parametrize("param", ["sort", "query", "page"])
def test_url_swap_base(param):
    """
    When we change a parameter, we should change the url
    :return:
    """


@pytest.mark.skip(reason="TODO")
def test_url_swap_multicol():
    """
    When we change multiple params, they should both be in the url
    :return:
    """


@pytest.mark.skip(reason="TODO")
def test_sort_url():
    """
    Sort should be like
    no sort: nothing in url
    ascending: sort=col
    descending: sort=-col
    """
