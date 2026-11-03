from pathlib import Path
from typing import Callable as C

import pytest
from sqlmodel import Session
from torrent_models import Torrent

from sciop.config import get_config
from sciop.models import Account, Dataset, DatasetPart
from sciop.types import Scopes


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


def test_upload_urls(upload, client, admin_auth_header):
    """Uploads can be created, edited, and read with urls"""
    ul = upload(urls="https://example.com/a\nhttps://example.com/b")

    res = client.get(get_config().api_prefix + f"/uploads/{ul.infohash}")
    assert res.status_code == 200
    assert res.json()["urls"] == ["https://example.com/a", "https://example.com/b"]

    new_urls = ["https://example.com/b", "https://example.com/c"]
    res = client.patch(
        get_config().api_prefix + f"/uploads/{ul.infohash}",
        json={"urls": new_urls},
        headers=admin_auth_header,
    )
    assert res.status_code == 200
    assert res.json()["urls"] == new_urls


def test_upload_urls_paginated(upload, client):
    """Upload urls are listed in their own paginated, sortable endpoint"""
    urls = [f"https://example.com/{i:03d}" for i in range(150)]
    ul = upload(urls=urls)

    res = client.get(get_config().api_prefix + f"/uploads/{ul.infohash}/urls")
    assert res.status_code == 200
    page_1 = res.json()
    assert [item["url"] for item in page_1["items"]] == urls[:100]

    res = client.get(get_config().api_prefix + f"/uploads/{ul.infohash}/urls?page=2")
    assert [item["url"] for item in res.json()["items"]] == urls[100:]

    res = client.get(get_config().api_prefix + f"/uploads/{ul.infohash}/urls?sort=-url&size=5")
    assert [item["url"] for item in res.json()["items"]] == urls[::-1][:5]

    res = client.get(
        get_config().api_prefix + f"/uploads/{ul.infohash}/urls", headers={"HX-Request": "true"}
    )
    assert res.status_code == 200
    assert f'id="url-table-{ul.infohash}"' in res.text
    assert urls[0] in res.text


@pytest.mark.parametrize(
    "scopes,n_urls,status",
    [([], 512, 200), ([], 513, 422), ([Scopes.upload], 513, 200)],
)
def test_upload_url_limits(
    scopes, n_urls, status, account, torrentfile, upload, dataset, client, get_auth_header
):
    """
    Accounts without upload permissions can add at most 512 urls,
    when creating or editing an upload
    """
    acct = account(scopes=scopes, username="limited")
    header = get_auth_header(acct.username)
    ds = dataset(slug="url-limits", is_approved=True)
    urls = [f"https://example.com/{i}" for i in range(n_urls)]

    created = client.post(
        get_config().api_prefix + "/uploads",
        headers=header,
        json={
            "infohash": torrentfile(account_=acct).infohash,
            "dataset_slug": ds.slug,
            "method": "By downloading it",
            "description": "It is an upload",
            "urls": urls,
        },
    )
    ul = upload(account_=acct, dataset_=ds)
    edited = client.patch(
        get_config().api_prefix + f"/uploads/{ul.infohash}", headers=header, json={"urls": urls}
    )

    for res in (created, edited):
        assert res.status_code == status
        if status == 422:
            assert res.json()["detail"][0]["loc"] == ["body", "urls"]


def test_upload_urls_ragged_page_metadata(upload, dataset, client):
    """
    Ragged pages report the size of the page they're on,
    including when there are no items
    """
    ds = dataset()
    empty = upload(dataset_=ds)
    res = client.get(get_config().api_prefix + f"/uploads/{empty.infohash}/urls")
    assert res.status_code == 200
    assert res.json()["items"] == []
    assert res.json()["size"] == 100
    assert res.json()["pages"] == 0

    ul = upload(dataset_=ds, urls=[f"https://example.com/{i}" for i in range(150)])
    page_1 = client.get(get_config().api_prefix + f"/uploads/{ul.infohash}/urls").json()
    assert (page_1["size"], page_1["pages"], len(page_1["items"])) == (100, 2, 100)
    page_2 = client.get(get_config().api_prefix + f"/uploads/{ul.infohash}/urls?page=2").json()
    assert (page_2["size"], page_2["pages"], len(page_2["items"])) == (1000, 2, 50)


def test_upload_urls_not_visible(upload, client):
    """Urls of uploads that the viewer can't see aren't listed"""
    ul = upload(urls=["https://example.com/a"], is_approved=False)
    res = client.get(get_config().api_prefix + f"/uploads/{ul.infohash}/urls")
    assert res.status_code == 404


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
