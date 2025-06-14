"""Plugin that needs to be used in order to use sciop testing fixtures"""

import argparse

import pytest
from pytest import MonkeyPatch

# import all fixtures
from sciop.testing.fixtures import *  # noqa: F403

mpatch = MonkeyPatch()


def pytest_sessionstart(session: pytest.Session) -> None:
    from sciop import models  # noqa: F401
    from sciop.config import get_config

    cfg = get_config()
    mpatch.setattr(cfg, "env", "test")
    mpatch.setattr(cfg.services.docs, "enabled", False)
    mpatch.setenv("SCIOP_ENV", "test")
    mpatch.setenv("SCIOP_SERVICES__DOCS__ENABLED", "false")


def pytest_sessionfinish(session: pytest.Session) -> None:
    global mpatch
    mpatch.undo()


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
