import pytest
from playwright.async_api import Page, expect

from ..fixtures.server import UvicornTestServer


@pytest.mark.parametrize("use_hash", ["v1_infohash", "v2_infohash", "short_hash"])
def test_uploads_urls(use_hash, client, upload):
    """Uploads can be reached from their v1, v2, and short hashes"""
    ul = upload()
    hash = getattr(ul.torrent, use_hash)
    res = client.get(f"/uploads/{hash}")
    assert res.status_code == 200


def test_no_show_unapproved(account, upload, client):
    acc = account()
    ul = upload(account=acc, is_approved=False)
    res = client.get(f"/uploads/{ul.infohash}")
    assert res.status_code == 404


def test_no_show_removed(account, upload, client, session):
    acc = account()
    ul = upload(account=acc)
    infohash = ul.infohash
    ul.is_removed = True
    session.add(ul)
    session.commit()
    session.refresh(ul)

    res = client.get(f"/uploads/{infohash}")
    assert res.status_code == 404


def test_no_include_unapproved(dataset, upload, client):
    """Unapproved uploads are not included in dataset uploads lists"""
    ds = dataset()
    unapproved = upload(dataset_=ds, is_approved=False)
    approved = upload(dataset_=ds, is_approved=True)
    res = client.get("/datasets/default/uploads")
    assert res.status_code == 200
    infohashes = [item["torrent"]["v2_infohash"] for item in res.json()["items"]]
    assert res.status_code == 200
    assert unapproved.infohash not in infohashes
    assert approved.infohash in infohashes


def test_no_include_removed(dataset, upload, client, session):
    """Removed uploads are not included in dataset uploads lists"""
    ds = dataset()
    removed = upload(dataset_=ds, is_approved=True)
    approved = upload(dataset_=ds, is_approved=True)
    removed_infohash = removed.infohash
    approved_infohash = approved.infohash
    removed.is_removed = True
    session.add(removed)
    session.commit()

    res = client.get("/datasets/default/uploads")
    assert res.status_code == 200
    assert removed_infohash not in res.text
    assert approved_infohash in res.text


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_scroll_files(torrentfile, upload, page: Page, run_server: UvicornTestServer):
    """
    Scrolling the file list loads more files.

    Correctness of file list is tested in test_api/test_upload,
    this just tests the interactive loading behavior.
    """
    tf = torrentfile(n_files=2000, total_size=2000 * (16 * 2**10))
    ul = upload(torrentfile_=tf)

    await page.goto(f"http://127.0.0.1:8080/uploads/{ul.infohash}")
    await expect(page.locator(".file-table tbody")).to_be_visible()
    # 102 because of the two hidden trigger elements
    await expect(page.locator(".file-table tr")).to_have_count(102)
    # scroll to fetch list
    await page.get_by_text("99.bin").scroll_into_view_if_needed()
    # wait for list items to be present
    await page.get_by_text("100.bin").scroll_into_view_if_needed()
    await expect(page.get_by_text("100.bin")).to_be_visible()
    # one of the hidden trigger elements is replaced, two more are added
    await expect(page.locator(".file-table tr")).to_have_count(1103)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_upload_edit_replace_torrent(
    page_as_admin: Page, torrent_pair, account, dataset, torrentfile, upload, tmp_path
):
    torrent_1, torrent_2 = torrent_pair
    page = page_as_admin

    assert torrent_1.infohash == torrent_2.infohash

    torrent_2_path = tmp_path / "torrent_2.torrent"
    torrent_2.write(torrent_2_path)

    acct1 = account(username="original_uploader", scopes=["upload"])
    ds = dataset(slug="duplicate-dataset", account_=acct1)
    tf1 = torrentfile(torrent=torrent_1, account_=acct1, v2_infohash=False)
    ul = upload(torrentfile_=tf1, account_=acct1, dataset_=ds)

    await page.goto(f"http://127.0.0.1:8080/uploads/{ul.infohash}")
    await expect(page.get_by_role("cell", name="http://example.com/announce")).not_to_be_visible()

    await page.get_by_role("link", name="Edit").click()
    await expect(page).to_have_url(f"http://127.0.0.1:8080/uploads/{ul.infohash}/edit")
    await page.get_by_role("button", name="Choose File").set_input_files(str(torrent_2_path))
    await page.get_by_role("button", name="Upload").click()
    # wait for the server to process
    await expect(page.locator("input#file_name")).to_have_value("torrent_2.torrent")
    await page.get_by_role("button", name="Submit").click()

    await expect(page).to_have_url(f"http://127.0.0.1:8080/uploads/{ul.infohash}")
    await expect(page.get_by_role("cell", name="udp://example.com/announce")).to_be_visible()
    await expect(page.get_by_role("cell", name="http://example.com/announce")).to_be_visible()


@pytest.mark.skip(reason="TODO")
def test_show_trackers():
    """
    Trackers are shown in the upload page
    """
    pass


@pytest.mark.skip(reason="TODO")
def test_show_tracker_stats():
    """
    Tracker stats are shown in the upload page
    """
    pass
