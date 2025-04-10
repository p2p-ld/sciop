import re

import pytest
from playwright.async_api import Page, expect

from sciop.models import DatasetPart


@pytest.mark.timeout(20)
@pytest.mark.playwright
@pytest.mark.asyncio(loop_scope="session")
async def test_add_one_part(default_db, page_as_admin: Page):
    """
    A single dataset part can be added with a form as admin
    """
    page: Page = page_as_admin
    await page.goto("http://127.0.0.1:8080/datasets/default")
    await expect(page).to_have_url(re.compile(r".*default.*"))

    add_one = page.locator(".add-one-button")
    await expect(add_one).to_be_enabled()
    await add_one.click()

    # create da part
    await page.locator('input[name="part_slug"]').fill("new-part")
    await page.locator('textarea[name="description"]').fill("A New Part")
    await page.locator('textarea[name="paths"]').fill("/one_path\n/two_path\n/three_path")
    await page.locator('.dataset-parts-add-container button[type="submit"]').click()

    # Open it
    await page.locator("#dataset-part-collapsible-default-new-part").click()

    # the paths should be there!
    # (api correctness tested elsewhere, this just tests the buttons)
    paths = page.locator("#dataset-part-collapsible-default-new-part .path-list code")
    await expect(paths).to_have_count(3)


@pytest.mark.timeout(20)
@pytest.mark.playwright
@pytest.mark.asyncio(loop_scope="session")
async def test_add_parts(default_db, page_as_admin):
    """
    A single dataset part can be added with a form as admin
    """
    page = page_as_admin
    await page.goto("http://127.0.0.1:8080/datasets/default")

    add_bulk = page.locator(".add-bulk-button")
    await expect(add_bulk).to_be_enabled()
    await add_bulk.click()

    await page.locator('textarea[name="parts"]').fill("one-part\ntwo-part\nthree-part")
    await page.locator('.dataset-parts-add-container button[type="submit"]').click()

    await expect(page.locator("#dataset-part-collapsible-default-one-part")).to_be_visible()
    await expect(page.locator("#dataset-part-collapsible-default-two-part")).to_be_visible()
    await expect(page.locator("#dataset-part-collapsible-default-three-part")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.skip(reason="todo")
def test_add_part_unauth(page_as_user, default_db):
    """
    A dataset part should be addable by a user without 'submit' scope,
    and then it is shown as being disabled
    """
    pass


def test_no_show_unapproved(dataset, client, session, account):
    """Unapproved dataset parts are not shown as their own pages"""
    acc = account()
    ds = dataset()
    ds.parts.append(DatasetPart(part_slug="unapproved-part", is_approved=False, account=acc))
    session.add(ds)
    session.commit()
    res = client.get("/datasets/default/unapproved-part")
    assert res.status_code == 404


def test_no_show_removed(dataset, client, session, account):
    """Unapproved dataset parts are not shown as their own pages"""
    acc = account()
    ds = dataset()
    ds.parts.append(DatasetPart(part_slug="removed-part", is_approved=True, account=acc))
    ds.parts[0].is_removed = True
    session.add(ds)
    session.commit()
    res = client.get("/datasets/default/removed-part")
    assert res.status_code == 404


def test_no_include_unapproved(client, dataset, session, account):
    """unapproved dataset parts are not shown in dataset parts lists"""
    acc = account()
    ds = dataset()
    ds.parts.append(DatasetPart(part_slug="unapproved-part", is_approved=False, account=acc))
    ds.parts.append(DatasetPart(part_slug="approved-part", is_approved=True, account=acc))
    session.add(ds)
    session.commit()
    res = client.get("/datasets/default/parts")
    assert res.status_code == 200
    assert "approved-part" in res.text
    assert "unapproved-part" not in res.text


def test_no_include_removed(client, dataset, session, account):
    """removed dataset parts are not shown in dataset parts lists"""
    acc = account()
    ds = dataset()
    ds.parts.append(DatasetPart(part_slug="removed-part", is_approved=True, account=acc))
    ds.parts.append(DatasetPart(part_slug="approved-part", is_approved=True, account=acc))
    ds.parts[0].is_removed = True
    session.add(ds)
    session.commit()
    res = client.get("/datasets/default/parts")
    assert res.status_code == 200
    assert "approved-part" in res.text
    assert "removed-part" not in res.text
