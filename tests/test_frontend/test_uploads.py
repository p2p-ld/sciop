import pytest


@pytest.mark.parametrize("use_hash", ["v1_infohash", "v2_infohash", "short_hash"])
def test_uploads_urls(use_hash, client, upload):
    """Uploads can be reached from their v1, v2, and short hashes"""
    ul = upload()
    hash = getattr(ul.torrent, use_hash)
    res = client.get(f"/uploads/{hash}")
    assert res.status_code == 200
