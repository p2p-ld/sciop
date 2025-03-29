import asyncio
import contextlib
import os
import socket
import time
from threading import Thread
from typing import Callable as C
from typing import Literal as L
from typing import Optional

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from sqlmodel import Session
from starlette.testclient import TestClient
from uvicorn import Config, Server
from webdriver_manager import firefox
from webdriver_manager.core.driver_cache import DriverCacheManager


class LazyCacheManager(DriverCacheManager):
    """Cache manager that doesn't fail if github ratelimit exceeded"""

    def find_driver(self, driver: firefox.GeckoDriver) -> Optional[str]:
        """Find driver by '{os_type}_{driver_name}_{driver_version}_{browser_version}'."""
        browser_type = driver.get_browser_type()
        browser_version = self._os_system_manager.get_browser_version_from_os(browser_type)
        if not browser_version:
            return None

        metadata = self.load_metadata_content()
        try:
            key = self.__get_metadata_key(driver)
            if key not in metadata:
                return None
        except Exception as e:
            if len(metadata.keys()) > 0:
                key = list(metadata.keys())[-1]
            else:
                raise e

        driver_info = metadata[key]
        path = driver_info["binary_path"]
        if not os.path.exists(path):
            return None

        path = driver_info["binary_path"]
        return path

    def __get_metadata_key(self, driver: firefox.GeckoDriver) -> str:
        if self._metadata_key:
            return self._metadata_key

        driver_version = self.get_cache_key_driver_version(driver)
        browser_version = driver.get_browser_version_from_os()
        browser_version = browser_version if browser_version else ""
        self._metadata_key = (
            f"{self.get_os_type()}_{driver.get_name()}_{driver_version}" f"_for_{browser_version}"
        )
        return self._metadata_key


@pytest.fixture()
def client(session: Session) -> TestClient:
    """Client that runs the lifespan actions"""
    from sciop.app import app
    from sciop.db import get_session

    def get_session_override() -> Session:
        return session

    app.dependency_overrides[get_session] = get_session_override

    return TestClient(app)


@pytest.fixture()
def client_lifespan(session: Session) -> TestClient:
    """Client that runs the lifespan actions"""
    from sciop.app import app
    from sciop.db import get_session

    def get_session_override() -> Session:
        return session

    app.dependency_overrides[get_session] = get_session_override

    with TestClient(app) as client:
        yield client


# This was copied from pytest-asyncio.
# Ref.: https://github.com/pytest-dev/pytest-asyncio/blob/25d9592286682bc6dbfbf291028ff7a9594cf283/pytest_asyncio/plugin.py#L525-L527  # noqa: E501
def _unused_port(socket_type: int) -> int:
    """Find an unused localhost port from 1024-65535 and return it."""
    with contextlib.closing(socket.socket(type=socket_type)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def unused_tcp_port() -> int:
    return _unused_port(socket.SOCK_STREAM)


class Server_(Server):
    """
    Borrowed from https://github.com/encode/uvicorn/discussions/1455
    """

    @contextlib.contextmanager
    def run_in_thread(self) -> None:
        thread = Thread(target=self.run)
        thread.start()
        try:
            while not self.started:
                time.sleep(1e-3)
            yield
        finally:
            self.should_exit = True
            thread.join()


class Firefox_(webdriver.Firefox):

    def wait_for(
        self,
        locator: str,
        by: By = By.ID,
        timeout: float = 3,
        type: L["visible", "clickable"] = "visible",
    ) -> WebElement:
        if type == "clickable":
            element_present = EC.element_to_be_clickable((by, locator))
        elif type == "visible":
            element_present = EC.visibility_of_element_located((by, locator))
        else:
            raise ValueError("Dont know what ur type is lol")

        WebDriverWait(self, timeout).until(element_present)
        return self.find_element(by, locator)


@pytest.fixture()
async def run_server(session: Session) -> Server_:
    from sciop.app import app
    from sciop.db import get_session

    def get_session_override() -> Session:
        return session

    app.dependency_overrides[get_session] = get_session_override

    config = Config(
        app=app,
        port=8080,
        workers=1,
        reload=False,
        access_log=False,
        log_config=None,
    )
    server = Server_(config=config)
    await asyncio.sleep(0.1)
    with server.run_in_thread():
        yield server


@pytest.fixture(scope="session")
def driver_executable_path() -> str:
    try:
        return firefox.GeckoDriverManager(cache_manager=LazyCacheManager()).install()
    except ValueError as e:
        pytest.skip(f"couldn't download webdriver {str(e)}")


@pytest.fixture()
async def driver(
    run_server: Server_, request: pytest.FixtureRequest, driver_executable_path: str
) -> webdriver.Firefox:
    executable_path = driver_executable_path
    options = FirefoxOptions()
    options.add_argument("--disable-dev-shm-usage")
    if not request.config.getoption("--show-browser"):
        options.add_argument("--headless")
        options.headless = True
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    _service = FirefoxService(executable_path=executable_path)
    try:
        browser = Firefox_(service=_service, options=options)
        browser.set_window_size(1920, 1080)
        browser.maximize_window()
        browser.implicitly_wait(0.25)
        # hail mary to avoid some thread synchronization problems
        await asyncio.sleep(0.25)

        yield browser

    finally:
        if "browser" in locals():
            browser.close()
            browser.quit()

        await asyncio.sleep(0.25)


@pytest.fixture()
async def driver_as_admin(driver: webdriver.Firefox, admin_auth_header: dict) -> webdriver.Firefox:
    driver.get("http://127.0.0.1:8080/login")

    username = driver.find_element(By.ID, "username")
    wait = WebDriverWait(driver, timeout=3)
    wait.until(lambda _: username.is_displayed())
    username.send_keys("admin")
    password = driver.find_element(By.ID, "password")
    password.send_keys("adminadmin12")
    submit = driver.find_element(By.ID, "login-button")
    submit.click()
    username_greeting = driver.find_element(By.CLASS_NAME, "self-greeting")
    wait = WebDriverWait(driver, timeout=3)
    wait.until(lambda _: username_greeting.is_displayed())
    return driver


@pytest.fixture()
async def driver_as_user(driver: webdriver.Firefox, account: C) -> webdriver.Firefox:
    """Driver as a regular user with no privs"""
    _ = account(username="user", password="userpassword123")
    driver.get("http://127.0.0.1:8080/login")
    username = driver.find_element(By.ID, "username")
    wait = WebDriverWait(driver, timeout=3)
    wait.until(lambda _: username.is_displayed())
    username.send_keys("user")
    password = driver.find_element(By.ID, "password")
    password.send_keys("userpassword123")
    submit = driver.find_element(By.ID, "login-button")
    submit.click()
    username_greeting = driver.find_element(By.CLASS_NAME, "self-greeting")
    wait = WebDriverWait(driver, timeout=3)
    wait.until(lambda _: username_greeting.is_displayed())
    return driver
