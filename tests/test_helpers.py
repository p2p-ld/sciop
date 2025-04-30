from sciop.helpers.diff import flatten_dict, unflatten_dict


def test_nest_unnest():
    """
    Nesting and unnnesting a dict works
    """
    unflat = {"a": 1, "b": {"c": 2, "d.e": 3, "f": {"g": 4}}, "h": [5, 6, 7]}
    flat = {"a": 1, "b.c": 2, "b.d\\.e": 3, "b.f.g": 4, "h": [4, 5, 6]}
    assert flatten_dict(unflat) == flat
    assert unflatten_dict(flat) == unflat
