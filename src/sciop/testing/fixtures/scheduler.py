import pytest_asyncio
from _pytest.monkeypatch import MonkeyPatch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import Engine

import sciop.scheduler.main


@pytest_asyncio.fixture(loop_scope="function")
async def clean_scheduler(monkeypatch: "MonkeyPatch", engine: Engine) -> AsyncIOScheduler:
    """Ensure scheduler state is clean during a test function"""
    sciop.scheduler.main.remove_all_jobs()
    sciop.scheduler.main.shutdown()
    yield
    sciop.scheduler.main.remove_all_jobs()
    sciop.scheduler.main.shutdown()
