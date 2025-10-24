from typing import Callable as C

import pytest
from sqlmodel import select
from starlette.testclient import TestClient
from torrent_models import Torrent

from sciop import crud
from sciop.config import get_config
from sciop.models import TorrentFile, Upload, UploadCreate
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
            get_config().api_prefix + "/torrents", headers=header, files={"file": f}
        )

    assert response.status_code == 200
    created = response.json()
    if "v1_infohash" in hashes:
        assert created["v1_infohash"] == hashes["v1_infohash"]
    if "v2_infohash" in hashes:
        assert created["v2_infohash"] == hashes["v2_infohash"]
    assert created["version"] == version


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
            get_config().api_prefix + "/torrents",
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
    ds = dataset(session_=session)
    tfile = tmp_path / "test.torrent"
    torrent_.write(tfile)
    with open(tfile, "rb") as f:
        response = client.post(
            get_config().api_prefix + "/torrents",
            headers=header,
            files={"file": ("filename.torrent", f, "application/x-bittorrent")},
        )
        assert response.status_code == 200

    ul = UploadCreate(
        infohash=torrent_.v1_infohash,
    )

    res = client.post(
        f"{get_config().api_prefix}/datasets/{ds.slug}/uploads",
        headers=header,
        json=ul.model_dump(),
    )
    assert res.status_code == 200
    ul = crud.get_upload_from_infohash(infohash=torrent_.v1_infohash, session=session)
    assert not ul.is_approved
    assert ul.needs_review


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
            get_config().api_prefix + "/torrents",
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
            get_config().api_prefix + "/torrents",
            headers=header,
            files={"file": (new_torrent_path.name, f, "application/x-bittorrent")},
        )
        assert response.status_code == 400

    assert "identical torrent file" in response.json()["detail"]["msg"]


@pytest.mark.parametrize("has_permission", [False, True])
def test_replace_duplicate_with_force(
    client,
    upload,
    dataset,
    account,
    torrentfile,
    get_auth_header,
    tmp_path,
    has_permission,
    session,
    torrent_pair,
):
    """
    When uploading a torrent file with `force`, we can replace one with a matching infohash
    """
    torrent_1, torrent_2 = torrent_pair
    torrent_2_path = tmp_path / "default_torrent_2.torrent"
    torrent_2.write(torrent_2_path)
    assert torrent_1.v1_infohash == torrent_2.v1_infohash

    # the first one should already exist as an upload
    acct1 = account(username="original_uploader", scopes=["upload"])
    ds = dataset(slug="duplicate-dataset", account_=acct1)
    tf1 = torrentfile(torrent=torrent_1, account_=acct1)
    ul = upload(torrentfile_=tf1, account_=acct1, dataset_=ds)
    existing_tf = ul.torrent
    existing_torrent_path = existing_tf.filesystem_path
    assert existing_torrent_path.exists()
    assert len(ul.torrent.trackers) == 1

    # try and upload a new one
    if has_permission:
        acct2 = account(username="new_uploader", scopes=["upload", "review"])
    else:
        acct2 = account(username="new_uploader", scopes=["upload"])
    header = get_auth_header("new_uploader")
    with open(torrent_2_path, "rb") as f:
        response = client.post(
            get_config().api_prefix + "/torrents/?force=true",
            headers=header,
            files={"file": (torrent_2_path.name, f, "application/x-bittorrent")},
        )

    if not has_permission:
        assert response.status_code == 403
        assert "identical torrent file" in response.json()["detail"]["msg"]
        assert "current account does not have permissions" in response.json()["detail"]["msg"]
        return

    assert response.status_code == 200
    # reload the whole upload object
    ul_reload = session.exec(select(Upload).where(Upload.upload_id == ul.upload_id)).first()
    # added the new trackers (and thus are the new torrent file)
    assert ul.torrent.v1_infohash == ul_reload.torrent.v1_infohash
    assert len(ul_reload.torrent.trackers) == 2
    # kept the old account associated with the upload
    assert ul_reload.account == acct1
    # and the API response is correct
    res_data = response.json()
    assert res_data["announce_urls"] == [
        "udp://example.com/announce",
        "http://example.com/announce",
    ]


def test_files_ragged_pagination(client, upload, torrentfile):
    """
    Torrent files do ragged pagination:
    When no size is specified:
    first page is 100 files,
    every other page is 1000 files

    When a size is specified, all pages are equal
    """
    tf = torrentfile(n_files=2000, total_size=2000 * (16 * 2**10))
    ul = upload(torrentfile_=tf)
    res = client.get(get_config().api_prefix + f"/uploads/{ul.infohash}/files")
    assert res.status_code == 200
    page_1 = res.json()
    assert len(page_1["items"]) == 100
    assert page_1["items"][0]["path"] == "0.bin"
    assert page_1["items"][-1]["path"] == "99.bin"

    res = client.get(get_config().api_prefix + f"/uploads/{ul.infohash}/files/?page=2")
    assert res.status_code == 200
    page_2 = res.json()
    assert len(page_2["items"]) == 1000
    assert page_2["items"][0]["path"] == "100.bin"
    assert page_2["items"][-1]["path"] == "1099.bin"

    res = client.get(get_config().api_prefix + f"/uploads/{ul.infohash}/files/?size=500")
    assert res.status_code == 200
    page_1_sized = res.json()
    assert len(page_1_sized["items"]) == 500
    assert page_1_sized["items"][0]["path"] == "0.bin"
    assert page_1_sized["items"][-1]["path"] == "499.bin"

    res = client.get(get_config().api_prefix + f"/uploads/{ul.infohash}/files/?size=500&page=2")
    assert res.status_code == 200
    page_2_sized = res.json()
    assert len(page_2_sized["items"]) == 500
    assert page_2_sized["items"][0]["path"] == "500.bin"
    assert page_2_sized["items"][-1]["path"] == "999.bin"


def test_webseeds_on_creation(
    client, dataset, torrent: C[[], Torrent], tmp_path, account, get_auth_header, session
):
    """
    Webseeds are created from an uploaded torrent file, and we can get them from the API
    """
    tf = torrent()
    uploader = account(username="uploader", scopes=["upload"])
    header = get_auth_header(uploader.username)

    ds = dataset(slug="test-upload-webseeds", is_approved=True)
    webseeds = ["https://example.com/files/data", "https://backup.example.com/files/data"]
    torrent_path = tmp_path / "my_torrent.torrent"

    tf.url_list = webseeds
    tf.write(torrent_path)
    with open(torrent_path, "rb") as f:
        response = client.post(
            get_config().api_prefix + "/torrents", headers=header, files={"file": f}
        )

    assert response.status_code == 200
    assert [ws["url"] for ws in response.json()["webseeds"]] == webseeds

    # associate with an upload and get from upload api
    response = client.post(
        get_config().api_prefix + "/uploads",
        headers=header,
        json={
            "infohash": tf.v2_infohash,
            "dataset_slug": ds.slug,
        },
    )
    response.raise_for_status()

    ws_response = client.get(get_config().api_prefix + f"/uploads/{tf.v2_infohash}/webseeds")
    ws_response.raise_for_status()
    get_ws = ws_response.json()
    get_urls = [ws["url"] for ws in get_ws]
    assert get_urls == webseeds
    assert all(ws["status"] == "in_original" for ws in get_ws)
    assert all(ws["torrent"] == tf.v2_infohash for ws in get_ws)
    assert all(ws["account"] == uploader.username for ws in get_ws)
