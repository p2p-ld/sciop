import asyncio

import httpx
import pytest
from bs4 import BeautifulSoup as bs
from playwright.async_api import Page, expect

from sciop.config import get_config


@pytest.mark.timeout(15)
@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_request(default_db, page_as_admin: Page):
    page = page_as_admin
    await page.goto("http://127.0.0.1:8080/request")
    await asyncio.sleep(0.1)

    title = "Test Item"
    slug = "test-item"
    publisher = "test publisher"
    tags = "tag1, tag2"

    await page.locator("#request-form-title").fill(title)
    await page.locator("#request-form-slug").fill(slug)
    await page.locator("#request-form-publisher").fill(publisher)
    await page.locator("#request-form-tags").fill(tags)
    await page.locator(".form-button").click()
    await page.wait_for_timeout(250)
    await expect(page).to_have_url("http://127.0.0.1:8080/datasets/test-item")

    async with httpx.AsyncClient() as client:
        res = await client.get(f"http://127.0.0.1:8080{get_config().api_prefix}/datasets/test-item")
    dataset = res.json()
    assert dataset["title"] == title
    assert dataset["slug"] == slug
    assert dataset["publisher"] == publisher
    assert dataset["tags"] == tags.split(", ")


@pytest.mark.timeout(20)
@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.playwright
async def test_rm_subform_items(page_as_admin: Page):
    page = page_as_admin
    await page.goto("http://127.0.0.1:8080/request")
    await page.wait_for_timeout(250)

    title = "Test Item"
    slug = "test-item"
    publisher = "test publisher"
    tags = "tag1, tag2"

    expected_ext_ids = [
        {"type": "doi", "identifier": "10.10000/real-1"},
        {"type": "doi", "identifier": "10.10000/real-2"},
    ]
    rm_ext_ids = {"type": "doi", "identifier": "10.10000/bad-1"}

    await page.locator("#request-form-title").fill(title)
    await page.locator("#request-form-slug").fill(slug)
    await page.locator("#request-form-publisher").fill(publisher)
    await page.locator("#request-form-tags").fill(tags)

    ext_ids = page.locator('.form-item[data-field-name="external_identifiers"]')

    # add first item
    await ext_ids.locator(".add-subform-button").click()
    await ext_ids.locator('[name="external_identifiers[0].type"]').select_option(
        expected_ext_ids[0]["type"]
    )
    await ext_ids.locator('[name="external_identifiers[0].identifier"]').fill(
        expected_ext_ids[0]["identifier"]
    )

    # add second item
    await ext_ids.locator(".add-subform-button").click()
    # await expect(page.locator("#external_identifiers[1].type")).to_be_visible()
    await ext_ids.locator('[name="external_identifiers[1].type"]').select_option(rm_ext_ids["type"])
    await ext_ids.locator('[name="external_identifiers[1].identifier"]').fill(
        rm_ext_ids["identifier"]
    )

    # but then delete it
    await ext_ids.locator('.close-button[data-idx="1"]').click()

    # assert it's no longer there
    await expect(page.locator('[name="external_identifiers[1].type"]')).not_to_be_visible()

    # add the third item
    await ext_ids.locator(".add-subform-button").click()

    await ext_ids.locator('[name="external_identifiers[2].type"]').select_option(
        expected_ext_ids[1]["type"]
    )
    await ext_ids.locator('[name="external_identifiers[2].identifier"]').fill(
        expected_ext_ids[1]["identifier"]
    )

    # submit
    await page.locator(".form-button").click()
    await expect(page).to_have_url("http://127.0.0.1:8080/datasets/test-item")

    # extract dois from infobox
    infobox_keys = await page.locator(".infobox-key").all()
    infobox_vals = await page.locator(".infobox-value").all()
    infobox = [
        {"key": await key.text_content(), "value": await val.text_content()}
        for key, val in zip(infobox_keys, infobox_vals)
    ]
    dois = [item["value"] for item in infobox if item["key"] == "doi"]
    assert len(dois) == 2
    assert all([expected["identifier"] in dois for expected in expected_ext_ids])
    assert rm_ext_ids["identifier"] not in dois

    # and confirm with api copy
    async with httpx.AsyncClient() as client:
        res = await client.get(f"http://127.0.0.1:8080{get_config().api_prefix}/datasets/test-item")
    dataset = res.json()
    external_ids = dataset["external_identifiers"]
    api_dois = [ext["identifier"] for ext in external_ids]
    assert len(api_dois) == 2
    assert all([expected["identifier"] in api_dois for expected in expected_ext_ids])
    assert rm_ext_ids["identifier"] not in api_dois


def test_datetimes(client, admin_auth_header):
    """
    Request form datetime fields should be datetime
    :param client:
    :param admin_auth_header:
    :return:
    """
    datetimes = (
        "dataset_created_at",
        "dataset_updated_at",
        "last_seen_at",
    )
    res = client.get("/request", headers=admin_auth_header)
    assert res.status_code == 200
    soup = bs(res.text, "html.parser")
    for field in datetimes:
        elem = soup.select_one(f'input[name="{field}"]')
        assert elem.attrs["type"] == "datetime-local"
