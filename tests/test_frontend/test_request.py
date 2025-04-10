import asyncio
import os

import pytest
import requests
from bs4 import BeautifulSoup as bs
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from sciop.config import config


@pytest.mark.timeout(15)
@pytest.mark.xfail("IN_CI" in os.environ, reason="selenium still too flaky for CI")
@pytest.mark.playwright
async def test_request(default_db, driver_as_admin):
    driver_as_admin.get("http://127.0.0.1:8080/request")
    # allow htmx to load and execute
    await asyncio.sleep(0.15)

    title = "Test Item"
    slug = "test-item"
    publisher = "test publisher"
    tags = "tag1, tag2"
    element_present = EC.presence_of_element_located((By.ID, "request-form-title"))
    WebDriverWait(driver_as_admin, 3).until(element_present)

    driver_as_admin.find_element(By.ID, "request-form-title").send_keys(title)
    driver_as_admin.find_element(By.ID, "request-form-slug").send_keys(slug)
    driver_as_admin.find_element(By.ID, "request-form-publisher").send_keys(publisher)
    driver_as_admin.find_element(By.ID, "request-form-tags").send_keys(tags)
    driver_as_admin.find_element(By.CLASS_NAME, "form-button").click()
    element_present = EC.presence_of_element_located((By.ID, "dataset-test-item"))
    WebDriverWait(driver_as_admin, 3).until(element_present)

    res = requests.get(f"http://127.0.0.1:8080{config.api_prefix}/datasets/test-item")
    dataset = res.json()
    assert dataset["title"] == title
    assert dataset["slug"] == slug
    assert dataset["publisher"] == publisher
    assert dataset["tags"] == tags.split(", ")


@pytest.mark.timeout(20)
@pytest.mark.xfail("IN_CI" in os.environ, reason="selenium still too flaky for CI")
@pytest.mark.playwright
async def test_rm_subform_items(driver_as_admin):
    driver_as_admin.get("http://127.0.0.1:8080/request")
    # allow htmx to load and execute
    await asyncio.sleep(0.15)
    element_present = EC.presence_of_element_located((By.ID, "request-form-title"))
    WebDriverWait(driver_as_admin, 3).until(element_present)

    title = "Test Item"
    slug = "test-item"
    publisher = "test publisher"
    tags = "tag1, tag2"

    expected_ext_ids = [
        {"type": "doi", "identifier": "10.10000/real-1"},
        {"type": "doi", "identifier": "10.10000/real-2"},
    ]
    rm_ext_ids = {"type": "doi", "identifier": "10.10000/bad-1"}

    driver_as_admin.find_element(By.ID, "request-form-title").send_keys(title)
    driver_as_admin.find_element(By.ID, "request-form-slug").send_keys(slug)
    driver_as_admin.find_element(By.ID, "request-form-publisher").send_keys(publisher)
    driver_as_admin.find_element(By.ID, "request-form-tags").send_keys(tags)

    ext_ids = driver_as_admin.find_element(
        By.CSS_SELECTOR, '.form-item[data-field-name="external_identifiers"]'
    )

    # add first item
    ext_ids.find_element(By.CLASS_NAME, "add-subform-button").click()
    await asyncio.sleep(0.1)
    element_present = EC.presence_of_element_located(
        (By.ID, "request-form-external_identifiers[0].type")
    )
    WebDriverWait(driver_as_admin, 1).until(element_present)
    ext_ids.find_element(By.ID, "request-form-external_identifiers[0].type").send_keys(
        expected_ext_ids[0]["type"]
    )
    ext_ids.find_element(By.ID, "request-form-external_identifiers[0].identifier").send_keys(
        expected_ext_ids[0]["identifier"]
    )

    # add second item
    ext_ids.find_element(By.CLASS_NAME, "add-subform-button").click()
    await asyncio.sleep(0.1)
    element_present = EC.presence_of_element_located(
        (By.ID, "request-form-external_identifiers[1].type")
    )
    WebDriverWait(driver_as_admin, 1).until(element_present)
    ext_ids.find_element(By.ID, "request-form-external_identifiers[1].type").send_keys(
        rm_ext_ids["type"]
    )
    ext_ids.find_element(By.ID, "request-form-external_identifiers[1].identifier").send_keys(
        rm_ext_ids["identifier"]
    )

    # but then delete it
    ext_ids.find_element(By.CSS_SELECTOR, '.close-button[data-idx="1"]').click()
    await asyncio.sleep(0.1)

    # assert it's no longer there
    element_not_present = EC.invisibility_of_element_located(
        (By.ID, "request-form-external_identifiers[1].type")
    )
    assert element_not_present(driver_as_admin)

    # add the third item
    ext_ids.find_element(By.CLASS_NAME, "add-subform-button").click()
    await asyncio.sleep(0.1)
    element_present = EC.presence_of_element_located(
        (By.ID, "request-form-external_identifiers[2].type")
    )
    WebDriverWait(driver_as_admin, 1).until(element_present)
    ext_ids.find_element(By.ID, "request-form-external_identifiers[2].type").send_keys(
        expected_ext_ids[1]["type"]
    )
    ext_ids.find_element(By.ID, "request-form-external_identifiers[2].identifier").send_keys(
        expected_ext_ids[1]["identifier"]
    )

    # submit
    driver_as_admin.find_element(By.CLASS_NAME, "form-button").click()
    await asyncio.sleep(0.1)
    element_present = EC.presence_of_element_located((By.ID, "dataset-test-item"))
    WebDriverWait(driver_as_admin, 3).until(element_present)

    # extract dois from infobox
    infobox_keys = driver_as_admin.find_elements(By.CSS_SELECTOR, ".infobox-key")
    infobox_vals = driver_as_admin.find_elements(By.CSS_SELECTOR, ".infobox-value")
    infobox = [{"key": key.text, "value": val.text} for key, val in zip(infobox_keys, infobox_vals)]
    dois = [item["value"] for item in infobox if item["key"] == "doi"]
    assert len(dois) == 2
    assert all([expected["identifier"] in dois for expected in expected_ext_ids])
    assert rm_ext_ids["identifier"] not in dois

    # and confirm with api copy
    res = requests.get(f"http://127.0.0.1:8080{config.api_prefix}/datasets/test-item")
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
