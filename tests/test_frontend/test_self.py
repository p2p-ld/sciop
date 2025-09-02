import pytest
from playwright.async_api import Page, expect

from sciop.models import Account


@pytest.mark.playwright
@pytest.mark.asyncio(loop_scope="session")
async def test_account_admin(page_as_admin: Page, account, session):
    page = page_as_admin
    rando: Account = account(username="rando")
    assert not rando.has_scope("upload")

    await page.goto("http://127.0.0.1:8080/self/admin")
    await expect(page.locator("#rando-scope-upload")).to_have_class("toggle-button")
    await page.locator("#rando-scope-upload").click()
    await expect(page.locator("#rando-scope-upload")).to_have_class("toggle-button checked")

    session.refresh(rando)
    assert rando.has_scope("upload")

    await page.locator("#rando-scope-upload").click()
    await expect(page.locator("#rando-scope-upload")).to_have_class("toggle-button")


@pytest.mark.skip()
def test_show_unapproved_self_datasets():
    pass


@pytest.mark.skip()
def test_show_unapproved_self_dataset_parts():
    pass


@pytest.mark.skip()
def test_show_unapproved_self_uploads():
    pass
