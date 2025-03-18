import pytest
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from sciop.config import config


@pytest.mark.timeout(15)
@pytest.mark.selenium
async def test_request(default_db, driver_as_admin):
    driver_as_admin.get("http://127.0.0.1:8080/request")
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
