import argparse
import contextlib
import shutil
import sys

import pytest
from _pytest.monkeypatch import MonkeyPatch
from _pytest.python import Function

mpatch = MonkeyPatch()
mpatch.setenv("SCIOP_ENV", "test")

from sqlalchemy.orm import sessionmaker

from .fixtures import *
from .fixtures import LOGS_DIR, TMP_DIR, TORRENT_DIR


# --------------------------------------------------
# hooks
# --------------------------------------------------
def pytest_addoption(parser: argparse.ArgumentParser) -> None:
    parser.addoption(
        "--echo-queries",
        action="store_true",
        default=False,
        help="Echo queries made by SQLAlchemy to stdout (use with -s)",
    )
    parser.addoption(
        "--persist-output",
        action="store_true",
        default=False,
        help="Persist test output data (torrents, logs) between tests in the __tmp__ directory, ",
    )
    parser.addoption(
        "--persist-db",
        action="store_true",
        default=False,
        help="Persist the database after and between tests."
        "Also prevents rolling back db state after tests, so it will almost certainly break "
        "a full test run. Typically used when running a single test or set of tests with -k"
        "Also typically used with --file-db",
    )
    parser.addoption(
        "--file-db",
        action="store_true",
        default=False,
        help="Use a file-based sqlite db rather than in-memory db (default)",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    TMP_DIR.mkdir(exist_ok=True)
    TORRENT_DIR.mkdir(exist_ok=True)


def pytest_collection_modifyitems(items: list[Function]) -> None:
    for item in items:
        if any(["page" in fixture_name for fixture_name in getattr(item, "fixturenames", ())]):
            item.add_marker("playwright")


def pytest_collection_finish(session: pytest.Session) -> None:
    from sciop.middleware import limiter

    limiter.enabled = False


def pytest_sessionfinish(session: pytest.Session) -> None:
    global mpatch
    mpatch.undo()

    if not session.config.getoption("--persist-output") and not session.config.getoption(
        "--persist-db"
    ):
        shutil.rmtree(TMP_DIR, ignore_errors=True)
    elif not session.config.getoption("--persist-output"):
        shutil.rmtree(TORRENT_DIR, ignore_errors=True)
        shutil.rmtree(LOGS_DIR, ignore_errors=True)


# --------------------------------------------------
# global fixtures
# --------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def monkeypatch_config(monkeypatch_session: "MonkeyPatch", request: pytest.FixtureRequest) -> None:
    """
    After we are able to declare environmental variables in session start,
    patch the config
    """
    from sqlmodel import Session, create_engine

    from sciop import config

    if request.config.getoption("--file-db"):
        db_path = TMP_DIR / "db.test.sqlite"
        db_path.unlink(missing_ok=True)
    else:
        db_path = None

    new_config = config.Config(
        env="test",
        db=db_path,
        torrent_dir=TORRENT_DIR,
        secret_key="12345",
        clear_jobs=True,
        base_url="http://localhost:8080",
        enable_versions=True,
    )
    new_config.logs.dir = LOGS_DIR
    new_config.logs.level_file = "DEBUG"
    new_config.logs.level_stdout = "DEBUG"
    new_config.site_stats.enabled = True
    monkeypatch_session.setattr(config, "config", new_config)
    for key, module in sys.modules.items():
        if not key.startswith("sciop.") and not key.startswith("tests."):
            continue
        with contextlib.suppress(AttributeError):
            monkeypatch_session.setattr(module, "config", new_config)

    from sciop import db

    engine_kwargs = {}
    if request.config.getoption("--file-db"):
        engine_kwargs = {
            "pool_size": new_config.db_pool_size,
            "max_overflow": new_config.db_overflow_size,
        }
    if request.config.getoption("--echo-queries"):
        engine_kwargs["echo"] = True

    engine = create_engine(str(new_config.sqlite_path), **engine_kwargs)
    monkeypatch_session.setattr(db, "engine", engine)
    maker = sessionmaker(class_=Session, autocommit=False, autoflush=False, bind=engine)
    monkeypatch_session.setattr(db, "maker", maker)
    db.create_tables(engine, check_migrations=False)
