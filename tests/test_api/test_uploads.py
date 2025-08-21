from pathlib import Path
from typing import Callable as C

import pytest
from sqlmodel import Session
from torrent_models import Torrent

from sciop.config import get_config
from sciop.models import Account, Dataset, DatasetPart


@pytest.mark.parametrize("infohash_type", ["v1_infohash", "v2_infohash"])
def test_upload(
    dataset: C[..., Dataset],
    torrent: C[..., Torrent],
    client,
    uploader: Account,
    get_auth_header,
    infohash_type: str,
    tmp_path: Path,
) -> None:
    """We can create an upload!"""
    ds = dataset(slug="test-upload", is_approved=True)

    header = get_auth_header(uploader.username)
    torrent_ = torrent()
    tfile = tmp_path / "test.torrent"
    torrent_.write(tfile)

    with open(tfile, "rb") as f:
        response = client.post(
            get_config().api_prefix + "/torrents", headers=header, files={"file": f}
        )
    response.raise_for_status()

    upload_create = {
        "infohash": response.json().get(infohash_type),
        "dataset_slug": ds.slug,
        "method": "By downloading it",
        "description": "It is an upload",
    }
    response = client.post(get_config().api_prefix + "/uploads", headers=header, json=upload_create)
    response.raise_for_status()
    created = response.json()
    assert created["method"] == upload_create["method"]
    assert created["description"] == upload_create["description"]
    assert created["torrent"][infohash_type] == upload_create["infohash"]
    assert created["dataset"] == ds.slug
    assert created["account"] == uploader.username


@pytest.mark.parametrize("part_slugs", (["part-1"], ["part-2", "part-3"]))
def test_upload_dataset_parts(
    dataset: C[..., Dataset],
    torrent: C[..., Torrent],
    client,
    uploader: Account,
    get_auth_header,
    tmp_path: Path,
    session: Session,
    part_slugs: list[str],
) -> None:
    """We can create an upload!"""
    ds = dataset(slug="test-upload", is_approved=True)
    ds.parts = [DatasetPart(part_slug=slug) for slug in part_slugs]
    session.add(ds)
    session.commit()

    header = get_auth_header(uploader.username)
    torrent_ = torrent()
    tfile = tmp_path / "test.torrent"
    torrent_.write(tfile)

    with open(tfile, "rb") as f:
        response = client.post(
            get_config().api_prefix + "/torrents", headers=header, files={"file": f}
        )
    response.raise_for_status()

    upload_create = {
        "infohash": response.json().get("v1_infohash"),
        "dataset_slug": ds.slug,
        "part_slugs": part_slugs,
        "method": "By downloading it",
        "description": "It is an upload",
    }
    response = client.post(get_config().api_prefix + "/uploads", headers=header, json=upload_create)
    response.raise_for_status()
    created = response.json()
    assert created["method"] == upload_create["method"]
    assert created["description"] == upload_create["description"]
    assert created["torrent"]["v1_infohash"] == upload_create["infohash"]
    assert created["dataset"] == ds.slug
    assert created["dataset_parts"] == part_slugs


@pytest.mark.skip()
def test_webseed_add(upload, uploader, client, get_auth_header, mocker):
    """
    Adding webseed with upload privs should add the webseed to the db and the torrent,
    and queue the webseed for validation
    """
    mocker.patch("sciop.scheduler.main.queue_job")
    from sciop.scheduler.main import queue_job

    url = "https://example.com/data"
    ul = upload()
    header = get_auth_header(uploader.username)
    response = client.post(
        get_config().api_prefix + f"/uploads/{ul.infohash}/webseeds",
        headers=header,
        json={"url": url},
    )
    response.raise_for_status()
    res = response.json()
    assert res["is_approved"]
    queue_job.assert_called_once_with(
        "validate_webseed", kwargs={"infohash": ul.infohash, "url": url}
    )


def test_webseed_add_unauthed(upload, account, client, get_auth_header, mocker):
    """
    Adding webseed without upload privs adds it, marks it pending approval,
    and doesn't trigger validation
    """
    mocker.patch("sciop.scheduler.main.queue_job")
    from sciop.scheduler.main import queue_job

    url = "https://example.com/data"
    ul = upload()
    acct = account(username="rando")
    header = get_auth_header(acct.username)
    response = client.post(
        get_config().api_prefix + f"/uploads/{ul.infohash}/webseeds",
        headers=header,
        json={"url": url},
    )
    response.raise_for_status()
    res = response.json()
    assert not res["is_approved"]
    assert res["status"] == "pending_review"
    queue_job.assert_not_called()


def test_webseed_approve_validates(upload, account, client, get_auth_header, mocker):
    """
    Approving a webseed causes it to be validated.
    """

    mocker.patch("sciop.api.routes.review.queue_job")
    from sciop.api.routes.review import queue_job

    url = "https://example.com/data"
    ul = upload()
    acct = account(username="rando")
    header = get_auth_header(acct.username)
    response = client.post(
        get_config().api_prefix + f"/uploads/{ul.infohash}/webseeds",
        headers=header,
        json={"url": url},
    )
    response.raise_for_status()

    admin = account(username="admin", scopes=("admin",))
    header = get_auth_header(admin.username)
    response = client.post(
        get_config().api_prefix + f"/uploads/{ul.infohash}/webseeds/approve",
        headers=header,
        json={"url": url},
    )
    response.raise_for_status()
    queue_job.assert_called_once_with(
        "validate_webseed", kwargs={"infohash": ul.infohash, "url": url}
    )


def test_webseed_uploader_deletes(upload, account, client, get_auth_header, mocker):
    """
    The uploader should be able to delete a webseed even if they didn't add it.
    """
    mocker.patch("sciop.scheduler.main.queue_job")

    url = "https://example.com/data"
    uploader = account(username="uploader", scopes=("upload",))
    rando = account(username="rando", scopes=("upload",))
    uploader_header = get_auth_header(uploader.username)
    rando_header = get_auth_header(rando.username)

    ul = upload(account_=uploader)
    response = client.post(
        get_config().api_prefix + f"/uploads/{ul.infohash}/webseeds",
        headers=rando_header,
        json={"url": url},
    )
    response.raise_for_status()

    response = client.delete(
        get_config().api_prefix + f"/uploads/{ul.infohash}/webseeds/?url={url}",
        headers=uploader_header,
    )
    response.raise_for_status()

    get = client.get(
        get_config().api_prefix + f"/uploads/{ul.infohash}/webseeds",
    )
    assert get.json() == []


@pytest.mark.parametrize("username", ["rando", "has_upload", None])
def test_webseed_delete_unauthed(
    username: str | None, upload, account, client, get_auth_header, mocker
):
    """
    We can't delete webseeds if we are just a rando or logged out
    """
    mocker.patch("sciop.scheduler.main.queue_job")

    url = "https://example.com/data"
    uploader = account(username="uploader", scopes=("upload",))
    ul = upload(account=uploader)
    uploader_header = get_auth_header(uploader.username)
    response = client.post(
        get_config().api_prefix + f"/uploads/{ul.infohash}/webseeds",
        headers=uploader_header,
        json={"url": url},
    )
    response.raise_for_status()

    if username is None:
        header = {}
    elif username == "has_upload":
        rando = account(username=username, scopes=("upload",))
        header = get_auth_header(rando.username)
    else:
        rando = account(username=username)
        header = get_auth_header(rando.username)

    response = client.delete(
        get_config().api_prefix + f"/uploads/{ul.infohash}/webseeds/?url={url}",
        headers=header,
    )
    assert response.status_code in (401, 403)
