import pytest
from torf._errors import MetainfoError

from sciop.config import config
from sciop.models.torrent import TorrentVersion

from ..fixtures.paths import DATA_DIR


@pytest.mark.parametrize(
    "torrent,hashes,version",
    [
        (
            DATA_DIR / "test_v1.torrent",
            {"v1_infohash": "eb0346b69a319c08918f62415c6fb9953403a44d"},
            TorrentVersion.v1,
        ),
        (
            DATA_DIR / "test_v2.torrent",
            {"v2_infohash": "1c3cd9e5be97985fff25710ef2ca96c363fe0dd1ddb49a6d4c6eacdaae283a0e"},
            TorrentVersion.v2,
        ),
        (
            DATA_DIR / "test_hybrid.torrent",
            {
                "v1_infohash": "de8854f5f9d2f9c36f88447949f313f71d229815",
                "v2_infohash": "8c05ed0ecb7ccf9c9fe8261f9c49cdf456cbf2f69a28a2eae759dd7b866dc350",
            },
            TorrentVersion.hybrid,
        ),
    ],
)
def test_upload_torrent_infohash(
    torrent, hashes, version, client, uploader, get_auth_header
) -> None:
    """We can upload a torrent and the infohashes are correct"""
    header = get_auth_header()
    with open(torrent, "rb") as f:
        if version == TorrentVersion.v2:
            with pytest.raises(MetainfoError):
                _ = client.post(
                    config.api_prefix + "/upload/torrent", headers=header, files={"file": f}
                )
            return
        else:
            response = client.post(
                config.api_prefix + "/upload/torrent", headers=header, files={"file": f}
            )

    if version in (TorrentVersion.v1, TorrentVersion.hybrid):
        assert response.status_code == 200
        created = response.json()
        if "v1_infohash" in hashes:
            assert created["v1_infohash"] == hashes["v1_infohash"]
        if "v2_infohash" in hashes:
            assert created["v2_infohash"] == hashes["v2_infohash"]
        assert created["version"] == version
