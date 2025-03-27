import asyncio
import os

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from sciop.models import DatasetPart

from ..fixtures.server import Firefox_


def _wait_until_located(
    driver: Firefox_, locator: str, by: By = By.ID, timeout: float = 10, type: str = "visible"
) -> None:
    if type == "clickable":
        element_present = EC.element_to_be_clickable((by, locator))
    else:
        element_present = EC.visibility_of_element_located((by, locator))

    WebDriverWait(driver, timeout).until(element_present)


@pytest.mark.timeout(20)
@pytest.mark.asyncio
@pytest.mark.xfail("IN_CI" in os.environ, reason="selenium still too flaky for CI")
@pytest.mark.selenium
async def test_add_part(default_db, driver_as_admin):
    """
    A single dataset part can be added with a form as admin
    """
    driver: Firefox_ = driver_as_admin
    driver.get("http://127.0.0.1:8080/datasets/default")
    # wait to ensure htmx loads and executes
    await asyncio.sleep(0.15)

    _wait_until_located(driver, "add-one-button", by=By.CLASS_NAME, type="clickable")
    add_one = driver.find_element(By.CLASS_NAME, "add-one-button")
    add_one.click()

    _wait_until_located(driver, "dataset-parts-add-container", By.CLASS_NAME)
    assert driver.find_element(By.CLASS_NAME, "dataset-parts-add-container")
    driver.find_element(By.CSS_SELECTOR, 'input[name="part_slug"]').send_keys("new-part")
    driver.find_element(By.CSS_SELECTOR, 'textarea[name="description"]').send_keys("A New Part")
    driver.find_element(By.CSS_SELECTOR, 'textarea[name="paths"]').send_keys(
        "/one_path\n/two_path\n/three_path"
    )
    driver.find_element(
        By.CSS_SELECTOR, '.dataset-parts-add-container button[type="submit"]'
    ).click()

    _wait_until_located(driver, "dataset-part-collapsible-default-new-part")
    created_part = driver.find_element(By.ID, "dataset-part-collapsible-default-new-part")
    created_part.click()
    paths = created_part.find_elements(By.CSS_SELECTOR, ".path-list code")
    assert len(paths) == 3


@pytest.mark.timeout(20)
@pytest.mark.asyncio
@pytest.mark.xfail("IN_CI" in os.environ, reason="selenium still too flaky for CI")
@pytest.mark.selenium
async def test_add_parts(default_db, driver_as_admin):
    """
    A single dataset part can be added with a form as admin
    """
    driver: Firefox_ = driver_as_admin
    driver.get("http://127.0.0.1:8080/datasets/default")
    # wait to ensure htmx loads and executes
    await asyncio.sleep(0.15)

    _wait_until_located(driver, "add-bulk-button", by=By.CLASS_NAME, type="clickable")
    add_bulk = driver.find_element(By.CLASS_NAME, "add-bulk-button")
    add_bulk.click()

    _wait_until_located(driver, "dataset-parts-add-container", By.CLASS_NAME)
    slugs_input = driver.find_element(By.CSS_SELECTOR, 'textarea[name="parts"]')
    slugs_input.send_keys("one-part\ntwo-part\nthree-part")
    driver.find_element(
        By.CSS_SELECTOR, '.dataset-parts-add-container button[type="submit"]'
    ).click()

    _wait_until_located(driver, "dataset-part-collapsible-default-one-part")
    assert driver.find_element(By.ID, "dataset-part-collapsible-default-one-part")
    assert driver.find_element(By.ID, "dataset-part-collapsible-default-two-part")
    assert driver.find_element(By.ID, "dataset-part-collapsible-default-three-part")


@pytest.mark.selenium
@pytest.mark.skip(reason="todo")
def test_add_part_unauth(driver_as_user, default_db):
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
