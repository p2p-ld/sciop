import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable
from typing import Literal as L

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

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
