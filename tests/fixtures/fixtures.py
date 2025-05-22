import contextlib
import logging
import sys
from typing import Any
from typing import Callable as C

import pytest
import pytest_asyncio
from _pytest.monkeypatch import MonkeyPatch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from faker import Faker
from sqlalchemy import Engine

from sciop import scheduler
from sciop.models import Account, Dataset, TorrentFile, Upload

__all__ = [
    "clean_scheduler",
    "countables",
    "log_console_width",
    "monkeypatch_module",
    "monkeypatch_session",
    "set_config",
]


@pytest.fixture
def log_console_width(monkeypatch: "MonkeyPatch") -> None:
    """
    Set rich console width to be very wide so that log messages print on one line
    """
    root_logger = logging.getLogger("sciop")
    monkeypatch.setattr(root_logger.handlers[1].console, "width", 1000)


@pytest_asyncio.fixture(loop_scope="function")
async def clean_scheduler(monkeypatch: "MonkeyPatch", engine: Engine) -> AsyncIOScheduler:
    """Ensure scheduler state is clean during a test function"""
    scheduler.remove_all_jobs()
    scheduler.shutdown()
    yield
    scheduler.remove_all_jobs()
    scheduler.shutdown()


@pytest.fixture
def countables(
    dataset: C[..., Dataset],
    upload: C[..., Upload],
    torrentfile: C[..., TorrentFile],
    uploader: Account,
) -> list["Dataset"]:
    fake = Faker()
    datasets = []
    for _ in range(3):
        ds: Dataset = dataset(
            slug="-".join(fake.words(3)),
        )
        for _ in range(3):
            tf: TorrentFile = torrentfile(total_size=1000)
            tf.tracker_links[0].seeders = 5
            tf.tracker_links[0].leechers = 10
            upload(dataset_=ds, torrentfile_=tf)
        datasets.append(ds)
    return datasets


@pytest.fixture
def set_config(monkeypatch: MonkeyPatch) -> C:
    def _set_config(**kwargs: Any) -> None:
        for k, v in kwargs.items():
            for mod_name, mod in sys.modules.items():
                if not mod_name.startswith("sciop") and not mod_name.startswith("tests."):
                    continue
                with contextlib.suppress(AttributeError):
                    monkeypatch.setattr(mod.config, k, v)

    return _set_config


@pytest.fixture(scope="session")
def monkeypatch_session() -> MonkeyPatch:
    """
    Monkeypatch you can use at the session scope!
    """
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture(scope="module")
def monkeypatch_module() -> MonkeyPatch:
    """
    Monkeypatch you can use at the session scope!
    """
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()
