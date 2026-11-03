import pytest
from bs4 import BeautifulSoup
from playwright.async_api import Page, expect


def test_header_alert(client, set_config):
    """
    Instance header field should add an alert bar to the header.
    """
    alert = "Some alert text with [markdown](https://example.com)"
    set_config({"instance.alert": alert})
    response = client.get("/")
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    header = soup.select_one(".site-header")
    alert = header.select_one(".alert-content .markdown")
    assert alert.text == "Some alert text with markdown"
    assert alert.select_one("a").attrs["href"] == "https://example.com"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_mobile_nav_menu(page: Page, run_server):
    """
    On small screens the nav links are folded into a menu that can be opened and closed,
    and the menu is closed when switching to the wide layout
    """
    await page.set_viewport_size({"width": 390, "height": 600})
    await page.goto("http://127.0.0.1:8080/")
    toggle = page.get_by_role("button", name="Menu")
    datasets = page.locator("#nav-menu").get_by_role("link", name="Datasets")

    await expect(datasets).not_to_be_visible()
    await expect(page.get_by_role("link", name="Login")).to_be_visible()

    await toggle.click()
    await expect(datasets).to_be_visible()
    await page.keyboard.press("Tab")
    await expect(datasets).to_be_focused()
    await page.keyboard.press("Escape")
    await expect(datasets).not_to_be_visible()
    await expect(toggle).to_be_focused()

    await toggle.click()
    await page.set_viewport_size({"width": 1200, "height": 600})
    await expect(page.locator("#nav-menu:popover-open")).to_have_count(0)
    await expect(toggle).not_to_be_visible()
    await expect(datasets).to_be_visible()
