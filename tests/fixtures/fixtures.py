import logging
from typing import Callable as C

import pytest
from _pytest.monkeypatch import MonkeyPatch
from faker import Faker

from sciop.models import Account, Dataset, TorrentFile, Upload

__all__ = [
    "countables",
    "log_console_width",
    "monkeypatch_module",
    "monkeypatch_session",
]


@pytest.fixture
def log_console_width(monkeypatch: "MonkeyPatch") -> None:
    """
    Set rich console width to be very wide so that log messages print on one line
    """
    root_logger = logging.getLogger("sciop")
    monkeypatch.setattr(root_logger.handlers[1].console, "width", 1000)


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
