import asyncio
import contextlib
import socket
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Callable as C

import pytest
import pytest_asyncio
from playwright.async_api import BrowserContext, Page
from sqlmodel import Session
from starlette.testclient import TestClient
from uvicorn import Config, Server

if TYPE_CHECKING:
    from sciop.models import Token


@pytest.fixture()
def client(session: Session) -> TestClient:
    """Regular test client that doesn't run lifespan actions"""
    from sciop.app import app

    return TestClient(app)


@pytest.fixture(scope="module")
def client_module(session_module: Session) -> TestClient:
    from sciop.app import app

    return TestClient(app)


@pytest.fixture()
def client_lifespan(session: Session) -> TestClient:
    """Client that runs the lifespan actions"""
    from sciop.app import app

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


class UvicornTestServer(Server):
    """Uvicorn test server
    https://stackoverflow.com/a/64454876/13113166
    """

    def __init__(self, config: Config):
        """Create a Uvicorn test server

        Args:
            app (FastAPI, optional): the FastAPI app. Defaults to main.app.
            host (str, optional): the host ip. Defaults to '127.0.0.1'.
            port (int, optional): the port. Defaults to PORT.
        """
        self._startup_done = asyncio.Event()
        super().__init__(config=config)

    async def startup(self, sockets: list | None = None) -> None:
        """Override uvicorn startup"""
        await super().startup(sockets=sockets)
        self.config.setup_event_loop()
        self._startup_done.set()

    async def up(self) -> None:
        """Start up server asynchronously"""
        loop = asyncio.get_event_loop()
        self._serve_task = loop.create_task(self.serve())
        await self._startup_done.wait()

    async def down(self) -> None:
        """Shut down server asynchronously"""
        self.should_exit = True
        await self._serve_task


@pytest.fixture
async def run_server(session: Session) -> UvicornTestServer:
    from sciop.app import app

    config = Config(
        app=app,
        port=8080,
        workers=1,
        reload=False,
        access_log=False,
        log_config=None,
    )

    server = UvicornTestServer(config=config)
    await server.up()
    yield
    await server.down()


@pytest.fixture(scope="module")
async def run_server_module(session_module: Session) -> UvicornTestServer:
    from sciop.app import app

    config = Config(
        app=app,
        port=8080,
        workers=1,
        reload=False,
        access_log=False,
        log_config=None,
    )

    server = UvicornTestServer(config=config)
    await server.up()
    yield
    await server.down()


@pytest.fixture
async def context(context: BrowserContext) -> BrowserContext:
    context.set_default_timeout(10 * 1000)
    yield context


@pytest.fixture
async def page(page: Page) -> Page:
    page.set_default_navigation_timeout(10 * 1000)
    yield page


@pytest.fixture()
async def page_as_admin(
    run_server: UvicornTestServer, context: BrowserContext, admin_token: "Token", page: Page
) -> Page:
    await context.add_cookies(
        [
            {
                "name": "access_token",
                "value": admin_token.access_token,
                "path": "/",
                "domain": "127.0.0.1",
            }
        ]
    )
    return page


@pytest_asyncio.fixture(loop_scope="session")
async def page_as_user(
    context: BrowserContext, run_server: UvicornTestServer, account: C, page: Page
) -> Page:
    """Driver as a regular user with no privs"""
    from sciop.api.auth import create_access_token

    acct = account(username="user", password="userpassword123")
    token = create_access_token(acct.account_id, expires_delta=timedelta(minutes=5))
    await context.add_cookies(
        [
            {
                "name": "access_token",
                "value": token,
                "path": "/",
                "domain": "127.0.0.1",
            }
        ]
    )
    return page
