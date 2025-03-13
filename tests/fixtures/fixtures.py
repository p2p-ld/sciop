import logging

import pytest
from _pytest.monkeypatch import MonkeyPatch
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from sciop import scheduler


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
