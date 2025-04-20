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

    await col.click()
    await expect(col).to_have_class("sort-link active ascending", timeout=10*1000)

    await expect(first).to_have_text(slugs[50])
    await expect(last).to_have_text(slugs[-1])

    await col.click()
    await expect(col).to_have_class("sort-link active descending")

    await expect(first).to_have_text(slugs[-51])
    await expect(last).to_have_text(slugs[0])


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


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_sort_joined(items, page: Page, run_server_module):
    """
    We can sort joined fields like upload file_name
    """
    await page.goto("http://127.0.0.1:8080/uploads/")
    col = page.locator('.sort-link[data-col="file_name"]')
    first = page.locator(".collapsible-table .collapsible:first-child .upload-title")
    last = page.locator(".collapsible-table .collapsible:last-child .upload-title")
    names = sorted([ul.file_name for ul in items[0]])

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
