import logging
from typing import Callable as C

import pytest
from _pytest.monkeypatch import MonkeyPatch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from faker import Faker

from sciop import scheduler
from sciop.models import Account, Dataset, TorrentFile, Upload


@pytest.fixture
def log_console_width(monkeypatch: "MonkeyPatch") -> None:
    """
    Set rich console width to be very wide so that log messages print on one line
    """
    root_logger = logging.getLogger("sciop")
    monkeypatch.setattr(root_logger.handlers[1].console, "width", 1000)


@pytest.fixture
async def clean_scheduler(monkeypatch: "MonkeyPatch") -> AsyncIOScheduler:
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
