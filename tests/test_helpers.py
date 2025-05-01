from sciop.helpers.collections import flatten_dict, merge_dicts, unflatten_dict


def test_nest_unnest():
    """
    Nesting and unnnesting a dict works
    """
    unflat = {"a": 1, "b": {"c": 2, "d.e": 3, "f": {"g": 4}}, "h": [5, 6, 7]}
    flat = {"a": 1, "b.c": 2, "b.d\\.e": 3, "b.f.g": 4, "h": [5, 6, 7]}
    assert flatten_dict(unflat) == flat
    assert unflatten_dict(flat) == unflat


def test_merge_dict():
    """
    merge-dict merges nested dicts!
    """
    a = {"a": 1, "b": {"c": 2, "d.e": 3, "f": {"g": 4}}, "h": [5, 6, 7]}
    b = {"a": 11, "b": {"c": 12, "f": {"z": 19}}}

    merged = merge_dicts(a, b)
    # simple overwrite
    assert merged["a"] == 11
    # leave unchanged keys alone
    assert merged["h"] == [5, 6, 7]
    assert merged["b"]["d.e"] == 3
    assert merged["b"]["f"]["g"] == 4
    # nested overwrites
    assert merged["b"]["c"] == 12
    # new value
    assert merged["b"]["f"]["z"] == 19
