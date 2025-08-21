import asyncio

import pytest
from playwright.async_api import Page, expect


@pytest.mark.playwright
@pytest.mark.asyncio(loop_scope="session")
async def test_add_webseed(page_as_admin, upload):
    """
    Adding a webseed... adds a webseed and refreshes the page to show it
    """
    ul = upload()
    page = page_as_admin

    await page.goto(f"http://127.0.0.1:8080/uploads/{ul.infohash}")
    await page.get_by_role("button", name="Add Webseed").click()
    # allow server to return
    await asyncio.sleep(0.1)

    await page.get_by_role("textbox", name="url").fill("https://example.com/data")
    await page.get_by_role("button", name="Submit").click()
    await asyncio.sleep(0.1)

    await expect(page.get_by_role("cell", name="https://example.com/data")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.asyncio(loop_scope="session")
async def test_delete_webseed(upload, torrentfile, page_as_admin):
    """
    Deleting a webseed removes it from the page
    """
    tf = torrentfile(webseeds=["https://example.com/data"])
    ul = upload(torrentfile_=tf)
    page: Page = page_as_admin

    locator = page.locator(selector=".webseeds-table td", has_text="https://example.com/data")

    await page.goto(f"http://127.0.0.1:8080/uploads/{ul.infohash}")
    await expect(locator).to_be_visible()
    await page.get_by_role("row", name="https://example.com/data @").get_by_role("button").click()
    await asyncio.sleep(0.1)
    await expect(locator).not_to_be_visible()
