import asyncio
import contextlib
import logging
import os
import socket
import sys
import time
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING, Callable
from typing import Literal as L

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine
from uvicorn import Config, Server
from webdriver_manager.firefox import GeckoDriverManager

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine

    from sciop.models import Account, Token

TMP_DIR = Path(__file__).parent / "__tmp__"
TMP_DIR.mkdir(exist_ok=True)


def pytest_sessionstart(session: pytest.Session) -> None:
    os.environ["SCIOP_SECRET_KEY"] = "12345"


def pytest_collection_finish(session: pytest.Session) -> None:
    from sciop.middleware import limiter

    limiter.enabled = False


@pytest.fixture(scope="session")
def monkeypatch_session() -> MonkeyPatch:
    """
    Monkeypatch you can use at the session scope!
    """
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture(autouse=True, scope="session")
def monkeypatch_config(monkeypatch_session: "MonkeyPatch") -> None:
    """
    After we are able to declare environmental variables in session start,
    patch the config
    """

    from sciop import config

    # do this once we write a way to figure out where the hell the db went
    # db_path = tmp_path / 'db.test.sqlite'

    db_path = TMP_DIR / "db.test.sqlite"
    db_path.unlink(missing_ok=True)

    new_config = config.Config(env="test", db=db_path, secret_key="12345")
    monkeypatch_session.setattr(config, "config", new_config)
    for key, module in sys.modules.items():
        if not key.startswith("sciop.") and not key.startswith("tests."):
            continue
        with contextlib.suppress(AttributeError):
            monkeypatch_session.setattr(module, "config", new_config)

    from sciop import db

    engine = create_engine(str(new_config.sqlite_path))
    monkeypatch_session.setattr(db, "engine", engine)
    maker = sessionmaker(class_=Session, autocommit=False, autoflush=False, bind=engine)
    monkeypatch_session.setattr(db, "maker", maker)


@pytest.fixture(scope="session", autouse=True)
def create_tables(monkeypatch_session: "MonkeyPatch", monkeypatch_config: None) -> None:
    from sciop.config import config
    from sciop.db import create_tables

    engine = create_engine(str(config.sqlite_path))
    create_tables(engine)


@pytest.fixture
def log_dir(monkeypatch: "MonkeyPatch", tmp_path: Path) -> Path:
    root_logger = logging.getLogger("sciop")
    base_file = tmp_path / "sciop.log"
    root_logger.handlers[0].close()
    monkeypatch.setattr(root_logger.handlers[0], "baseFilename", base_file)
    return base_file


@pytest.fixture
def log_console_width(monkeypatch: "MonkeyPatch") -> None:
    """
    Set rich console width to be very wide so that log messages print on one line
    """
    root_logger = logging.getLogger("sciop")
    monkeypatch.setattr(root_logger.handlers[1].console, "width", 1000)


@pytest.fixture(scope="session")
def client() -> TestClient:
    from sciop.main import app

    client = TestClient(app)
    return client


def _unused_port(socket_type: int) -> int:
    """Find an unused localhost port from 1024-65535 and return it."""
    with contextlib.closing(socket.socket(type=socket_type)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# This was copied from pytest-asyncio.
# Ref.: https://github.com/pytest-dev/pytest-asyncio/blob/25d9592286682bc6dbfbf291028ff7a9594cf283/pytest_asyncio/plugin.py#L525-L527  # noqa: E501
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


@pytest.fixture(scope="session")
async def run_server() -> Server_:
    from sciop.main import app

    config = Config(
        app=app,
        port=8080,
    )
    server = Server_(config=config)
    await asyncio.sleep(0.1)
    with server.run_in_thread():
        yield server


@pytest.fixture(scope="session")
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
    except WebDriverException as e:
        pytest.skip(str(e))


@pytest.fixture
def session() -> Session:
    from sciop.db import maker

    session = maker()
    yield session
    session.close()


@pytest.fixture
def default_dataset() -> dict:
    return {
        "title": "A Default Dataset",
        "slug": "a-default-dataset",
        "publisher": "Default Datasets Incorporated",
        "homepage": "https://example.com",
        "description": "You might not like it folks but this is it, "
        "this is the peak of default datasets",
        "source": "web",
        "urls": ["https://example.com/1", "https://example.com/2"],
        "tags": ["default", "dataset", "tags"],
    }


@pytest.fixture
def account(session: Session) -> "Account":

    from sciop import crud
    from sciop.models import AccountCreate

    account = crud.get_account(session=session, username="test_account")
    if not account:
        account = AccountCreate(username="test_account", password="a very strong password12")
        account = crud.create_account(session=session, account_create=account)
    return account


@pytest.fixture
def admin_user(session: Session) -> "Account":
    from sciop.db import create_admin

    return create_admin(session)


@pytest.fixture
def admin_token(client: "TestClient", admin_user: "Account") -> "Token":
    from sciop.config import config
    from sciop.models import Token

    response = client.post(
        config.api_prefix + "/login",
        data={"username": "admin", "password": "adminadmin12"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    return Token(**response.json())


@pytest.fixture
def admin_auth_header(admin_token: "Token") -> dict[L["Authorization"], str]:
    return {"Authorization": f"Bearer {admin_token.access_token}"}


@pytest.fixture
def recreate_models() -> Callable[[], "Engine"]:
    """Callable fixture to recreate models after any inline definitions of tables"""

    def _recreate_models() -> "Engine":
        from sciop.config import config

        engine = create_engine(str(config.sqlite_path))
        SQLModel.metadata.create_all(engine)
        return engine

    return _recreate_models
