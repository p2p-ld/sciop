from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlmodel import select

from sciop.models import Torrent, Upload

if TYPE_CHECKING:
    from ..fixtures.server import Firefox_

import pytest


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
def test_upload_from_download(page_as_admin: "Firefox_", torrent, dataset, session):
    """We can upload a torrent"""
    driver = driver_as_admin
    ds = dataset()
    t: Torrent = torrent()
    t.path.parent.mkdir(exist_ok=True, parents=True)
    t.write(t.path, overwrite=True)
    expected = {
        "method": "downloaded",
        "description": "it was downloaded",
        "infohash": t.infohash,
    }

    await page.goto("http://127.0.0.1:8080/datasets/default")
    # initiate upload partial
    driver.wait_for("upload-button", type="clickable").click()
    # upload file
    driver.wait_for('input[type="file"]', by=By.CSS_SELECTOR).send_keys(str(t.path))
    driver.find_element(By.CSS_SELECTOR, ".upload-form button[type=submit]").click()
    # input model fields
    driver.wait_for("upload-form-method").send_keys(expected["method"])
    driver.find_element(By.ID, "upload-form-description").send_keys(expected["description"])
    driver.find_element(By.ID, "submit-upload-button").click()
    # wait for upload to finalize
    driver.wait_for(f"upload-{t.infohash}")

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
