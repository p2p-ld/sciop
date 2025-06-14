import pytest_asyncio
from _pytest.monkeypatch import MonkeyPatch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import Engine

from sciop import scheduler


@pytest_asyncio.fixture(loop_scope="function")
async def clean_scheduler(monkeypatch: "MonkeyPatch", engine: Engine) -> AsyncIOScheduler:
    """Ensure scheduler state is clean during a test function"""
    scheduler.remove_all_jobs()
    scheduler.shutdown()
    yield
    scheduler.remove_all_jobs()
    scheduler.shutdown()
