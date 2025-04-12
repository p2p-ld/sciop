import pytest


@pytest.fixture()
def items():
    """The datasets we're gonna be searching and sorting"""
    pass


@pytest.mark.skip(reason="TODO")
def test_search_base():
    """We can search and subset queries"""


@pytest.mark.skip(reason="TODO")
def test_sort_base():
    """
    Basic sort behavior, we can sort by a single column
    :return:
    """


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
