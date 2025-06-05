import logging
from typing import Any
from typing import Callable as C

import pytest
import pytest_asyncio
from _pytest.monkeypatch import MonkeyPatch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from faker import Faker
from sqlalchemy import Engine

from sciop import get_config, scheduler
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


def _set_config(monkeypatch: MonkeyPatch, *args: Any, **kwargs: Any) -> None:
    config = get_config()
    if len(args) == 1 and isinstance(args[0], dict):
        kwargs = args[0]
    for k, v in kwargs.items():
        parts = k.split(".")
        if len(parts) == 1:
            monkeypatch.setattr(config, k, v)
        else:
            set_on = config
            for part in parts[:-1]:
                set_on = getattr(set_on, part)
            monkeypatch.setattr(set_on, parts[-1], v)


@pytest.fixture
def set_config(monkeypatch: MonkeyPatch) -> C:
    """
    Set a value on the config.

    Top-level values can be set like
    set_config(val="something")

    Nested values can be set like
    set_config({"nested.value": "something"})
    """

    def _inner(*args: Any, **kwargs: Any) -> None:
        return _set_config(monkeypatch, *args, **kwargs)

    return _inner


@pytest.fixture(scope="module")
def set_config_module(monkeypatch_module: MonkeyPatch) -> C:
    """
    Set a value on the config.

    Top-level values can be set like
    set_config(val="something")

    Nested values can be set like
    set_config({"nested.value": "something"})
    """

    def _inner(*args: Any, **kwargs: Any) -> None:
        return _set_config(monkeypatch_module, *args, **kwargs)

    return _inner


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
