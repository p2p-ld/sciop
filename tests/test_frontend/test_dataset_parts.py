import pytest
from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait


@pytest.mark.selenium
def test_add_part(driver_as_admin, default_db):
    """
    A single dataset part can be added with a form as admin
    """
    driver: Firefox = driver_as_admin
    driver.get("http://127.0.0.1:8080/datasets/default")

    add_one = driver.find_element(By.CLASS_NAME, "add-one-button")
    wait = WebDriverWait(driver, timeout=3)
    wait.until(lambda _: add_one.is_displayed())
    add_one.click()
    assert driver.find_element(By.CLASS_NAME, "dataset-parts-add-container")
    driver.find_element(By.CSS_SELECTOR, 'input[name="part_slug"]').send_keys("new-part")
    driver.find_element(By.CSS_SELECTOR, 'input[name="description"]').send_keys("A New Part")
    driver.find_element(By.CSS_SELECTOR, 'textarea[name="paths"]').send_keys(
        "/one_path\n/two_path\n/three_path"
    )
    driver.find_element(
        By.CSS_SELECTOR, '.dataset-parts-add-container button[type="submit"]'
    ).click()

    created_part = driver.find_element(By.ID, "dataset-part-collapsible-default-new-part")
    created_part.click()
    paths = created_part.find_elements(By.CSS_SELECTOR, ".path-list code")
    assert len(paths) == 3


@pytest.mark.selenium
def test_add_parts(driver_as_admin, default_db):
    """
    A single dataset part can be added with a form as admin
    """
    driver: Firefox = driver_as_admin
    driver.get("http://127.0.0.1:8080/datasets/default")

    add_bulk = driver.find_element(By.CLASS_NAME, "add-bulk-button")
    wait = WebDriverWait(driver, timeout=3)
    wait.until(lambda _: add_bulk.is_displayed())
    add_bulk.click()

    slugs_input = driver.find_element(By.CSS_SELECTOR, 'textarea[name="parts"]')
    slugs_input.send_keys("one-part\ntwo-part\nthree-part")
    driver.find_element(
        By.CSS_SELECTOR, '.dataset-parts-add-container button[type="submit"]'
    ).click()

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


@pytest.mark.skip()
def test_no_include_unapproved():
    pass


@pytest.mark.skip()
def test_no_include_removed():
    pass
