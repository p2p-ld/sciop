import pytest
from sqlmodel import select
from starlette.testclient import TestClient

from sciop import crud
from sciop.config import config
from sciop.models import TorrentFile, UploadCreate
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
    else:
        assert response.status_code == 415


@pytest.mark.parametrize("hx_request", [True, False])
def test_upload_trackerless(client, uploader, get_auth_header, torrent, hx_request, tmp_path):
    header = get_auth_header()
    if hx_request:
        header["HX-Request"] = "true"
    torrent_ = torrent(trackers=[])
    tfile = tmp_path / "test.torrent"
    torrent_.write(tfile)
    with open(tfile, "rb") as f:
        response = client.post(
            config.api_prefix + "/upload/torrent",
            headers=header,
            files={"file": ("filename.torrent", f, "application/x-bittorrent")},
        )
        assert response.status_code == 400
        if hx_request:
            assert response.headers["hx-retarget"] == "#error-modal-container"
            assert "text/html" in response.headers["content-type"]
            assert "must contain at least one tracker" in response.text
        else:
            msg = response.json()
            assert "must contain at least one tracker" in msg["detail"]["msg"]


def test_upload_noscope(
    client: TestClient, account, dataset, get_auth_header, torrent, session, tmp_path
):
    """Accounts without upload scope should be able to upload stuff"""
    acct = account()
    header = get_auth_header()
    torrent_ = torrent()
    ds = dataset()
    tfile = tmp_path / "test.torrent"
    torrent_.write(tfile)
    with open(tfile, "rb") as f:
        response = client.post(
            config.api_prefix + "/upload/torrent",
            headers=header,
            files={"file": ("filename.torrent", f, "application/x-bittorrent")},
        )
        assert response.status_code == 200

    ul = UploadCreate(
        infohash=torrent_.infohash,
    )

    res = client.post(
        f"{config.api_prefix}/datasets/{ds.slug}/uploads", headers=header, json=ul.model_dump()
    )
    assert res.status_code == 200
    ul = crud.get_upload_from_infohash(infohash=torrent_.infohash, session=session)
    assert not ul.is_approved
    assert ul.needs_review


@pytest.mark.selenium
def test_replace_orphaned_upload(
    client: TestClient, session, torrentfile, uploader, get_auth_header
):
    """
    Torrent files that are uploaded but not associated with an Upload
    should be replaced by a second upload
    """
    existing_tf: TorrentFile = torrentfile()
    existing_torrent_path = existing_tf.filesystem_path
    assert existing_tf.upload is None
    assert existing_torrent_path.exists()

    # make a copy with a different name to check
    new_torrent_path = existing_torrent_path.with_name("new.torrent")

    # try and upload
    header = get_auth_header()
    with open(existing_torrent_path, "rb") as f:
        response = client.post(
            config.api_prefix + "/upload/torrent",
            headers=header,
            files={"file": (new_torrent_path.name, f, "application/x-bittorrent")},
        )

        assert response.status_code == 200

    # This also tests our handling of infohashes since paths contain them
    assert not existing_torrent_path.exists()
    assert new_torrent_path.exists()

    tfs = session.exec(select(TorrentFile)).all()
    assert len(tfs) == 1
    assert tfs[0].file_name == new_torrent_path.name


def test_reject_duplicated_upload(client, upload, uploader, get_auth_header):
    """
    Torrent files that are associated with an upload should reject duplicates
    """
    ul = upload()
    existing_tf = ul.torrent
    existing_torrent_path = existing_tf.filesystem_path
    assert existing_torrent_path.exists()

    # make a copy with a different name to check
    new_torrent_path = existing_torrent_path.with_name("new.torrent")

    # try and upload
    header = get_auth_header()
    with open(existing_torrent_path, "rb") as f:
        response = client.post(
            config.api_prefix + "/upload/torrent",
            headers=header,
            files={"file": (new_torrent_path.name, f, "application/x-bittorrent")},
        )
        assert response.status_code == 400

    assert "identical torrent file" in response.json()["detail"]["msg"]
