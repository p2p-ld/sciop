import asyncio
from datetime import UTC, datetime, timedelta
from time import sleep

import pytest

from sciop import scheduler
from sciop.scheduler import add_date, add_interval, add_job, date, interval


def do_a_print():
    """https://www.youtube.com/shorts/qG1LG1gADog"""
    print(f"EVENT: {datetime.now().isoformat()}")


def _loglines(capsys) -> list[str]:
    stdout = capsys.readouterr().out
    lines = stdout.splitlines()
    return lines


def _eventlines(capsys) -> list[str]:
    lines = _loglines(capsys)
    return [line for line in lines if "EVENT" in line]


def test_add_job(client_lifespan, capsys):
    """
    do a single job
    """
    add_job(do_a_print)
    sleep(0.1)
    events = _eventlines(capsys)
    assert len(events) == 1


def test_add_interval(client_lifespan, capsys):
    """
    Do a job at an interval
    """
    add_interval(do_a_print, seconds=0.1)
    sleep(0.4)
    events = _eventlines(capsys)
    assert len(events) == 3


def test_add_date(client_lifespan, capsys):
    """
    Do a job at a time
    """
    todo = datetime.now() + timedelta(seconds=0.1)
    add_date(do_a_print, run_date=todo)
    sleep(0.3)
    events = _eventlines(capsys)
    assert len(events) == 1
    pass


@pytest.mark.skip(
    reason="there isn't really a good way to test cron tasks, so skipping until we figure it out"
)
def test_add_cron(client_lifespan, capsys):
    """
    Do a job with cron syntax
    """
    pass


@pytest.mark.asyncio
async def test_interval_decorator(capsys, clean_scheduler):
    """
    Interval decorators should let one declare a job before the scheduler exists,
    and then run it afterwards
    """
    assert scheduler.scheduler is None
    # can't use as a decorator because apscheduler needs to be able to serialize the function
    interval(seconds=0.1)(do_a_print)

    await asyncio.sleep(0.2)
    assert "do_a_print" in scheduler._TO_SCHEDULE
    assert len(_eventlines(capsys)) == 0

    # starting the scheduler should pick up the task
    scheduler.start_scheduler()
    await asyncio.sleep(0.25)

    events = _eventlines(capsys)
    assert len(events) == 2


@pytest.mark.asyncio
async def test_date_decorator(capsys, clean_scheduler):
    """
    Date decorators should let one declare a job before the scheduler exists,
    and then run it afterwards
    """
    assert scheduler.scheduler is None

    # can't use as a decorator because apscheduler needs to be able to serialize the function
    date(datetime.now(UTC) + timedelta(seconds=0.2))(do_a_print)

    await asyncio.sleep(0.1)
    assert "do_a_print" in scheduler._TO_SCHEDULE
    assert len(_eventlines(capsys)) == 0

    # starting the scheduler should pick up the task
    scheduler.start_scheduler()
    await asyncio.sleep(0.2)

    events = _eventlines(capsys)
    assert len(events) == 1


@pytest.mark.asyncio
async def test_disabled_decorator(capsys, clean_scheduler):
    """
    Decorators should be able to be toggled by their enabled parameter
    so they can be configured :)
    """
    assert scheduler.scheduler is None
    # can't use as a decorator because apscheduler needs to be able to serialize the function
    interval(seconds=0.01, enabled=False)(do_a_print)

    await asyncio.sleep(0.1)
    assert "do_a_print" not in scheduler._TO_SCHEDULE
    assert len(_eventlines(capsys)) == 0

    # starting the scheduler should NOT pick up the task
    scheduler.start_scheduler()
    await asyncio.sleep(0.1)

    events = _eventlines(capsys)
    assert len(events) == 0
