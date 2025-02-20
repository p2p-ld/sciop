import asyncio
import contextlib
import os
import socket
import time
from threading import Thread

import pytest
from selenium import webdriver
from selenium.common import WebDriverException
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from starlette.testclient import TestClient
from uvicorn import Server, Config
from webdriver_manager.firefox import GeckoDriverManager


@pytest.fixture()
def client(session) -> TestClient:
    """Client that runs the lifespan actions"""
    from sciop.main import app
    from sciop.db import get_session

    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    return TestClient(app)


@pytest.fixture()
def client_lifespan(session) -> TestClient:
    """Client that runs the lifespan actions"""
    from sciop.main import app
    from sciop.db import get_session

    def get_session_override():
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
async def run_server(session) -> Server_:
    from sciop.main import app
    from sciop.db import get_session

    def get_session_override():
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
async def driver(run_server: Server_) -> webdriver.Firefox:
    if os.environ.get("IN_CI", False):
        executable_path = "/snap/bin/firefox.geckodriver"
    else:
        executable_path = GeckoDriverManager().install()
    options = FirefoxOptions()
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.headless = True
    options.add_argument("--window-size=1920,1080")
    _service = FirefoxService(executable_path=executable_path)
    try:
        browser = webdriver.Firefox(service=_service, options=options)
        browser.set_window_size(1920, 1080)
        browser.maximize_window()
        browser.implicitly_wait(5)

        yield browser

        browser.close()
    except WebDriverException as e:
        pytest.skip(str(e))
