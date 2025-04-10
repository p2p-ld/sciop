import asyncio
import contextlib
import re
import socket
import time
from threading import Thread
from typing import Callable as C

import pytest
import pytest_asyncio
from playwright.async_api import BrowserContext, Page, expect
from sqlmodel import Session
from starlette.testclient import TestClient
from uvicorn import Config, Server


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

    def install_signal_handlers(self) -> None:
        pass

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


@pytest.fixture
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


@pytest.fixture
async def context(context: BrowserContext) -> BrowserContext:
    context.set_default_timeout(5 * 1000)
    yield context


@pytest.fixture
async def page(page: Page) -> Page:
    page.set_default_navigation_timeout(5 * 1000)
    yield page


@pytest.fixture()
async def page_as_admin(run_server: Server_, admin_auth_header: dict, page: Page) -> Page:
    await page.goto("http://127.0.0.1:8080/login")

    await page.locator("#username").fill("admin")
    await page.locator("#password").fill("adminadmin12")
    await page.locator("#login-button").click()

    await expect(page).to_have_url(re.compile(r".*self.*"))
    return page


@pytest_asyncio.fixture(loop_scope="session")
async def page_as_user(page: Page, run_server: Server_, account: C) -> Page:
    """Driver as a regular user with no privs"""
    _ = account(username="user", password="userpassword123")

    await page.locator("#username").fill("user")
    await page.locator("#password").fill("userpassword123")
    await page.locator("#login-button").click()

    await expect(page).to_have_url(re.compile(r".*self.*"))
    return page
