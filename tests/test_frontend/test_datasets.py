from datetime import UTC, datetime, timedelta

import pytest
from playwright.async_api import Page, expect
from sqlmodel import select
from torrent_models import Torrent

from sciop.models import Upload


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_upload_from_download(page_as_admin: "Page", torrent, dataset, session, tmp_path):
    """We can upload a torrent"""
    page = page_as_admin
    ds = dataset(session_=session)
    session.expire(ds)
    t: Torrent = torrent()
    tpath = tmp_path / "tmp.torrent"
    t.write(tpath)
    expected = {
        "method": "downloaded",
        "description": "it was downloaded",
        "infohash": t.v2_infohash,
    }

    await page.goto("http://127.0.0.1:8080/datasets/default")
    # initiate upload partial
    await page.locator("#upload-button").click()
    # upload file
    await page.locator('input[type="file"]').set_input_files(str(tpath))
    await page.locator(".upload-form button[type=submit]").click()
    # input model fields
    await page.locator("#upload-form-method").fill(expected["method"])
    await page.locator("#upload-form-description").fill(expected["description"])
    await page.locator("#submit-upload-button").click()
    # wait for upload to finalize
    await expect(page.locator(f"#upload-{t.v2_infohash}")).to_be_visible()

    upload = session.exec(select(Upload)).first()
    for k, v in expected.items():
        assert getattr(upload, k) == v


def test_no_show_unapproved(client, dataset):
    ds_ = dataset(slug="unapproved", is_approved=False)
    res = client.get("/datasets/unapproved")
    assert res.status_code == 404


def test_no_show_removed(client, dataset):
    ds_ = dataset(slug="removed", is_approved=True, is_removed=True)
    res = client.get("/datasets/removed")
    assert res.status_code == 404


def test_no_include_unapproved(client, dataset):
    """Unapproved datasets don't show up on the datasets page"""
    approved = dataset(slug="approved", is_approved=True)
    ds_ = dataset(slug="unapproved", is_approved=False)
    assert not ds_.is_approved
    res = client.get("/datasets/search")
    items = res.json()["items"]
    assert len(items) == 1
    slugs = [i["slug"] for i in items]
    assert "unapproved" not in slugs
    assert "approved" in slugs


def test_include_unapproved_if_reviewer(client, dataset, reviewer, get_auth_header):
    """Unapproved datasets do show up on the datasets page to reviewers"""
    header = get_auth_header(username=reviewer.username)
    approved = dataset(slug="approved", is_approved=True)
    ds_ = dataset(slug="unapproved", is_approved=False)
    assert not ds_.is_approved
    res = client.get("/datasets/search", headers=header)
    items = res.json()["items"]
    assert len(items) == 2
    slugs = [i["slug"] for i in items]
    assert "unapproved" in slugs
    assert "approved" in slugs


def test_no_include_removed(client, dataset):
    """Removed datasets are not included on the datasets page"""
    approved = dataset(slug="approved", is_approved=True, is_removed=False)
    ds_ = dataset(slug="removed", is_approved=True, is_removed=True)
    assert ds_.is_removed
    res = client.get("/datasets/search")
    items = res.json()["items"]
    assert len(items) == 1
    slugs = [i["slug"] for i in items]
    assert "removed" not in slugs
    assert "approved" in slugs


def test_no_include_removed_if_reviewer(client, dataset, reviewer, get_auth_header):
    """Removed datasets are not included on the datasets page, even to reviewers"""
    header = get_auth_header(username=reviewer.username)
    approved = dataset(slug="approved", is_approved=True)
    ds_ = dataset(slug="removed", is_approved=True, is_removed=True)
    assert ds_.is_removed
    res = client.get("/datasets/search", headers=header)
    items = res.json()["items"]
    assert len(items) == 1
    slugs = [i["slug"] for i in items]
    assert "removed" not in slugs
    assert "approved" in slugs


@pytest.mark.parametrize("when", ["future", "past"])
def test_last_seen_at(client, dataset, when):
    if when == "future":
        ds = dataset(last_seen_at=datetime.now(UTC) + timedelta(days=1))
    else:
        ds = dataset(last_seen_at=datetime.now(UTC) + timedelta(days=1))

    res = client.get("/datasets/default")
    assert res.status_code == 200
    if when == "future":
        assert "to be removed at" in res.text.lower()
    else:
        assert "removed at" in res.text.lower()
