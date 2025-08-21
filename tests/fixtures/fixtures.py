import logging
from itertools import count
from typing import Callable as C

import pytest
from _pytest.monkeypatch import MonkeyPatch
from faker import Faker
from sqlmodel import Session

from sciop.models import Account, Dataset, TorrentFile, Upload, Webseed

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
    session: Session,
) -> list["Dataset"]:
    fake = Faker()
    datasets = []
    seed_count = count(1)
    leech_count = count(5)
    for _ in range(3):
        ds: Dataset = dataset(
            slug="-".join(fake.words(3)),
        )
        for i in range(3):
            tf: TorrentFile = torrentfile(total_size=1000)
            if i == 0:
                tf.webseeds = [
                    Webseed(url="https://example.com/data", status="in_original", is_approved=True),
                    Webseed(
                        url="https://invalid.example.com/data", status="error", is_approved=True
                    ),
                    Webseed(
                        url="https://validated.example.com/data",
                        status="validated",
                        is_approved=True,
                    ),
                    Webseed(
                        url="https://in_progress.example.com/data",
                        status="in_progress",
                        is_approved=True,
                    ),
                ]
                session.add(tf)
                session.commit()
            tf.tracker_links[0].seeders = next(seed_count)
            tf.tracker_links[0].leechers = next(leech_count)
            tf.tracker_links[1].seeders = next(seed_count)
            tf.tracker_links[1].leechers = next(leech_count)
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
