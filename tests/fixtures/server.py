import asyncio
import contextlib
import os
import socket
import time
from threading import Thread
from typing import Callable as C

import pytest
from selenium import webdriver
from selenium.common import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from sqlmodel import Session
from starlette.testclient import TestClient
from uvicorn import Config, Server
from webdriver_manager.firefox import GeckoDriverManager


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
    if os.environ.get("IN_CI", False):
        executable_path = "/snap/bin/firefox.geckodriver"
    else:
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
        pytest.skip(str(e))
    finally:
        if "browser" in locals():
            browser.close()


@pytest.fixture()
async def driver_as_admin(driver: webdriver.Firefox, admin_auth_header: dict) -> webdriver.Firefox:
    driver.get("http://127.0.0.1:8080/login")
    username = driver.find_element(By.ID, "username")
    username.send_keys("admin")
    password = driver.find_element(By.ID, "password")
    password.send_keys("adminadmin12")
    submit = driver.find_element(By.ID, "login-button")
    submit.click()
    return driver


@pytest.fixture()
async def driver_as_user(driver: webdriver.Firefox, account: C) -> webdriver.Firefox:
    """Driver as a regular user with no privs"""
    _ = account(username="user", password="userpassword123")
    driver.get("http://127.0.0.1:8080/login")
    username = driver.find_element(By.ID, "username")
    username.send_keys("user")
    password = driver.find_element(By.ID, "password")
    password.send_keys("userpassword123")
    submit = driver.find_element(By.ID, "login-button")
    submit.click()
    return driver
