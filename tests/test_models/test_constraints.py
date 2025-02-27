import pytest

from sciop import models


@pytest.mark.parametrize(
    "model,field",
    [
        ("Account", "username"),
        ("Scope", "scope"),
        ("Dataset", "slug"),
        ("Tag", "tag"),
        ("TorrentFile", "v1_infohash"),
        ("TorrentFile", "v2_infohash"),
    ],
)
def test_known_uniques(model: str, field: str):
    """
    Regression test to protect against shit handling of mutiple `Field` annotations
    by sqlmodel
    """
    col = [c for c in getattr(models, model).__table__.columns if c.name == field][0]
    assert col.unique
