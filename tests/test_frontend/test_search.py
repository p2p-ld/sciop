import string
from itertools import cycle
from math import ceil

import pytest
from playwright.async_api import Page, expect
from sqlmodel import Session

from sciop.models import Dataset, Upload
from sciop.types import Threat


@pytest.fixture(scope="module")
def items(
    session_module: Session,
    dataset_module,
    upload_module,
    torrentfile_module,
    request: pytest.FixtureRequest,
) -> tuple[list[Upload], list[Dataset]]:
    """The datasets we're gonna be searching and sorting"""
    dataset = dataset_module
    upload = upload_module

    uploads = []
    datasets = []
    letters = cycle(string.ascii_lowercase)
    threats = cycle(v for v in Threat.__members__.values() if v is not Threat.unknown)
    for i in range(len(string.ascii_lowercase) * 3):
        letter = next(letters)
        letter = letter * max((ceil(((i + 1) / len(string.ascii_lowercase))) + 1), 2)

        ds = dataset(session_=session_module, slug=letter, threat=next(threats))
        t = torrentfile_module(session_=session_module, file_name=letter + ".torrent")
        ul = upload(session_=session_module, dataset_=ds, torrentfile_=t)

        uploads.append(ul)
        datasets.append(ds)

        # first one gets an extra upload to test sorting in nested partials
        if letter == "aa":
            t = torrentfile_module(session_=session_module, file_name="abab" + ".torrent")
            ul = upload(session_=session_module, dataset_=ds, torrentfile_=t)
            uploads.append(ul)
    return uploads, datasets


@pytest.mark.skip(reason="TODO")
def test_search_base():
    """We can search and subset queries"""


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_sort_base(items, page: Page, run_server_module):
    """
    Basic sort behavior, we can sort by a single column
    :return:
    """
    await page.goto("http://127.0.0.1:8080/datasets/")
    col = page.locator('.sort-link[data-col="slug"]')
    first = page.locator(".collapsible-table .collapsible:first-child .dataset-slug")
    last = page.locator(".collapsible-table .collapsible:last-child .dataset-slug")
    slugs = sorted([ds.slug for ds in items[1]])
    await col.click()

    await expect(col).to_have_class("sort-link active ascending")

    await expect(first).to_have_text(slugs[0])
    await expect(last).to_have_text(slugs[49])

    await col.click()
    await expect(col).to_have_class("sort-link active descending")

    await expect(first).to_have_text(slugs[-1])
    await expect(last).to_have_text(slugs[-50])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_sort_paging(items, page: Page, run_server_module):
    """
    Sorting should work through paging
    """
    await page.goto("http://127.0.0.1:8080/datasets/")
    col = page.locator('.sort-link[data-col="slug"]')
    first = page.locator(".collapsible-table .collapsible:first-child .dataset-slug")
    last = page.locator(".collapsible-table .collapsible:last-child .dataset-slug")
    slugs = sorted([ds.slug for ds in items[1]])

    await page.locator('.page-link[data-page="2"]').first.click()
    await expect(col).to_have_class("sort-link ", timeout=10 * 1000)
    await expect(col).to_have_attribute(
        name="hx-get", value="http://127.0.0.1:8080/datasets/search?page=2&sort=slug"
    )

    await col.click()
    await expect(col).to_have_class("sort-link active ascending", timeout=10 * 1000)

    await expect(first).to_have_text(slugs[50])
    await expect(last).to_have_text(slugs[-1])

    await col.click()
    await expect(col).to_have_class("sort-link active descending")

    await expect(first).to_have_text(slugs[-51])
    await expect(last).to_have_text(slugs[0])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_sort_numbers(items, page: Page, run_server_module, session_module):
    a = items[0][0]
    b = items[0][1]
    c = items[0][2]

    a.torrent.tracker_links[0].seeders = 7
    b.torrent.tracker_links[0].seeders = 70
    c.torrent.tracker_links[0].seeders = 8
    session_module.add(a)
    session_module.add(b)
    session_module.add(c)
    session_module.commit()

    await page.goto("http://127.0.0.1:8080/uploads/")
    col = page.locator('.sort-link[data-col="seeders"]')
    first = page.locator(".collapsible-table .collapsible:first-child .upload-title")
    second = page.locator(".collapsible-table .collapsible:nth-child(2) .upload-title")
    third = page.locator(".collapsible-table .collapsible:nth-child(3) .upload-title")

    await col.click()
    await expect(col).to_have_class("sort-link active ascending")
    await col.click()
    await expect(col).to_have_class("sort-link active descending")
    await expect(first).to_have_text(b.file_name)
    await expect(second).to_have_text(c.file_name)
    await expect(third).to_have_text(a.file_name)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_sort_multiparam(items, page: Page, run_server_module):
    """
    We can sort as well as subset with a query and use pagination at the same time
    """
    await page.goto("http://127.0.0.1:8080/datasets/")
    col = page.locator('.sort-link[data-col="slug"]')
    first = page.locator(".collapsible-table .collapsible:first-child .dataset-slug")
    last = page.locator(".collapsible-table .collapsible:last-child .dataset-slug")
    slugs = sorted([ds.slug for ds in items[1]])

    await col.click()
    await page.locator(".search-input").fill("aaa")

    await expect(first).to_have_text("aaa")
    await expect(last).to_have_text("aaaa")

    await col.click()
    await col.click()
    await page.wait_for_timeout(100)

    await expect(first).to_have_text("aaaa")
    await expect(last).to_have_text("aaa")


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_sort_enum(items, page: Page, run_server_module):
    """
    We can sort enums like threat
    """
    await page.goto("http://127.0.0.1:8080/datasets/")
    col = page.locator('.sort-link[data-col="threat"]')
    first = page.locator(".collapsible-table .collapsible:first-child .dataset-threat")

    await col.click()
    await expect(first).to_have_class("dataset-threat threat-dot threat-indefinite")
    await col.click()
    await expect(first).to_have_class("dataset-threat threat-dot threat-extinct")


@pytest.mark.parametrize("field", ("file_name", "size"))
@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_sort_joined(field, items, page: Page, run_server_module):
    """
    We can sort joined fields like upload file_name
    """
    await page.goto("http://127.0.0.1:8080/uploads/")
    col = page.locator(f'.sort-link[data-col="{field}"]')
    first = page.locator(".collapsible-table .collapsible:first-child .upload-title")
    last = page.locator(".collapsible-table .collapsible:last-child .upload-title")
    names = [ul.file_name for ul in sorted(items[0], key=lambda x: getattr(x, field))]

    await col.click()

    await expect(first).to_have_text(names[0])
    await expect(last).to_have_text(names[49])

    await col.click()

    await expect(first).to_have_text(names[-1])
    await expect(last).to_have_text(names[-50])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
@pytest.mark.parametrize("param", ["sort", "query", "page"])
async def test_url_swap_base(param, items, page: Page, run_server_module):
    """
    When we change a parameter, we should change the url
    :return:
    """
    await page.goto("http://127.0.0.1:8080/datasets/")
    if param == "sort":
        col = page.locator('.sort-link[data-col="slug"]')
        await col.click()
        await expect(page).to_have_url("http://127.0.0.1:8080/datasets/?sort=slug")
        await col.click()
        await expect(page).to_have_url("http://127.0.0.1:8080/datasets/?sort=-slug")
        await col.click()
        await col.click()
        await expect(page).to_have_url("http://127.0.0.1:8080/datasets/")
    elif param == "query":
        await page.locator(".search-input").fill("aaa")
        await expect(page).to_have_url("http://127.0.0.1:8080/datasets/?query=aaa")
    elif param == "page":
        await page.locator('.page-link[data-page="2"]').first.click()
        await expect(page).to_have_url("http://127.0.0.1:8080/datasets/?page=2")


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_url_swap_search_sort(items, page: Page, run_server_module):
    """
    When we change multiple params, they should both be in the url
    :return:
    """
    await page.goto("http://127.0.0.1:8080/datasets/")
    col = page.locator('.sort-link[data-col="slug"]')
    await col.click()
    await page.locator(".search-input").fill("a")
    await expect(page).to_have_url("http://127.0.0.1:8080/datasets/?query=a&sort=slug")
    await page.locator('.page-link[data-page="2"]').first.click()
    await page.wait_for_timeout(100)
    await expect(page).to_have_url("http://127.0.0.1:8080/datasets/?page=2&query=a&sort=slug")


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_sort_nested(items, page: Page, run_server_module):
    """
    Sortable items within sortable containers don't break!
    """
    await page.goto("http://localhost:8080/datasets/")
    await page.get_by_role("button", name="title No sort").click()
    await page.locator("#dataset-collapsible-aa").get_by_label("Expand/Collapse").click()
    # we don't break and fail to show the child
    await expect(page.get_by_text("aa.torrent")).to_be_visible()
    await expect(page.get_by_text("Internal Server Error")).not_to_be_visible()

    # we can still sort the items in the child
    await expect(
        page.locator(".upload-items .upload-collapsible:nth-child(1) .upload-title")
    ).to_have_text("abab.torrent")
    await expect(
        page.locator(".upload-items .upload-collapsible:nth-child(2) .upload-title")
    ).to_have_text("aa.torrent")
    await page.get_by_role("button", name="name No sort").click()
    await expect(
        page.locator(".upload-items .upload-collapsible:nth-child(1) .upload-title")
    ).to_have_text("aa.torrent")
    await expect(
        page.locator(".upload-items .upload-collapsible:nth-child(2) .upload-title")
    ).to_have_text("abab.torrent")
