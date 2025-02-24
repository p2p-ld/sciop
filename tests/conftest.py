import argparse
import contextlib
import sys

import pytest
from _pytest.monkeypatch import MonkeyPatch

mpatch = MonkeyPatch()
mpatch.setenv("SCIOP_SECRET_KEY", "12345")
mpatch.setenv("SCIOP_ENV", "test")


from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

from .fixtures import *
from .fixtures import TMP_DIR, TORRENT_DIR


def pytest_addoption(parser: argparse.ArgumentParser) -> None:
    parser.addoption(
        "--show-browser", action="store_true", default=False, help="Show browser in selenium tests"
    )


def pytest_sessionfinish(session: pytest.Session) -> None:
    global mpatch
    mpatch.undo()


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

    db_path = TMP_DIR / "db.test.sqlite"
    db_path.unlink(missing_ok=True)

    new_config = config.Config(env="test", db=db_path, torrent_dir=TORRENT_DIR, secret_key="12345")
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
