import asyncio
import contextlib
import os
import socket
import time
from threading import Thread
from typing import Callable as C
from typing import Optional

import pytest
from selenium import webdriver
from selenium.common import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.wait import WebDriverWait
from sqlmodel import Session
from starlette.testclient import TestClient
from uvicorn import Config, Server
from webdriver_manager import firefox
from webdriver_manager.core.download_manager import DownloadManager
from webdriver_manager.core.driver_cache import DriverCacheManager
from webdriver_manager.core.os_manager import OperationSystemManager


class GeckoDriver(firefox.GeckoDriver):
    """Override parent to not fail if we get github ratelimited..."""

    def get_latest_release_version(self) -> Optional[str]:
        try:
            resp = self._http_client.get(url=self.latest_release_url, headers=self.auth_header)
            return resp.json()["tag_name"]
        except Exception:
            # *completely fine pretty much all the time*
            return None


class GeckoDriverManager(firefox.GeckoDriverManager):
    def __init__(
        self,
        version: Optional[str] = None,
        name: str = "geckodriver",
        url: str = "https://github.com/mozilla/geckodriver/releases/download",
        latest_release_url: str = "https://api.github.com/repos/mozilla/geckodriver/releases/latest",
        mozila_release_tag: str = "https://api.github.com/repos/mozilla/geckodriver/releases/tags/{0}",
        download_manager: Optional[DownloadManager] = None,
        cache_manager: Optional[DriverCacheManager] = None,
        os_system_manager: Optional[OperationSystemManager] = None,
    ):
        kwargs = locals()
        _ = kwargs.pop("self")
        super().__init__(
            version=version,
            name=name,
            url=url,
            latest_release_url=latest_release_url,
            mozila_release_tag=mozila_release_tag,
            download_manager=download_manager,
            cache_manager=cache_manager,
            os_system_manager=os_system_manager,
        )

        self.driver = GeckoDriver(
            driver_version=version,
            name=name,
            url=url,
            latest_release_url=latest_release_url,
            mozila_release_tag=mozila_release_tag,
            http_client=self.http_client,
            os_system_manager=os_system_manager,
        )


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
    )
    server = Server_(config=config)
    await asyncio.sleep(0.1)
    with server.run_in_thread():
        yield server


@pytest.fixture()
async def driver(run_server: Server_, request: pytest.FixtureRequest) -> webdriver.Firefox:
    # if os.environ.get("IN_CI", False):
    #     executable_path = "/snap/bin/firefox.geckodriver"
    # else:
    executable_path = GeckoDriverManager().install()
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
        browser = webdriver.Firefox(service=_service, options=options)
        browser.set_window_size(1920, 1080)
        browser.maximize_window()
        browser.implicitly_wait(5)

        yield browser

    except WebDriverException as e:
        if os.environ.get("IN_CODEBERG_CI", False):
            pytest.skip(str(e))
        else:
            raise e
    finally:
        if "browser" in locals():
            browser.close()
            browser.quit()


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
