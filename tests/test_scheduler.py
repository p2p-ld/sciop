import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest
from apscheduler.events import EVENT_JOB_EXECUTED

import sciop.scheduler.main
import sciop.scheduler.rpc
from sciop.logging import init_logger
from sciop.scheduler import (
    add_date,
    add_interval,
    add_job,
    date,
    get_queued_jobs,
    get_scheduler,
    interval,
    queue,
    queue_job,
    start_scheduler,
)

_EVENTS = 0


def do_a_print():
    """https://www.youtube.com/shorts/qG1LG1gADog"""
    print(f"EVENT: {datetime.now().isoformat()}")


def sleep_for_a_bit(arg: str = "sup"):
    logger = init_logger("sleep")
    logger.warning(arg)
    time.sleep(1)


def _loglines(capsys) -> list[str]:
    stdout = capsys.readouterr().out
    lines = stdout.splitlines()
    return lines


def _eventlines(capsys) -> list[str]:
    lines = _loglines(capsys)
    return [line for line in lines if "EVENT" in line]


async def test_add_job(client_lifespan, capsys):
    """
    do a single job
    """
    add_job(do_a_print)
    await asyncio.sleep(0.1)
    events = _eventlines(capsys)
    assert len(events) == 1


async def test_add_interval(client_lifespan, capsys):
    """
    Do a job at an interval
    """
    add_interval(do_a_print, seconds=0.01)
    await asyncio.sleep(0.2)
    events = _eventlines(capsys)
    # we're not testing precision here
    assert len(events) >= 5


async def test_add_date(client_lifespan, capsys):
    """
    Do a job at a time
    """
    todo = datetime.now() + timedelta(seconds=0.1)
    add_date(do_a_print, run_date=todo)
    await asyncio.sleep(0.3)
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
    assert get_scheduler() is None
    # can't use as a decorator because apscheduler needs to be able to serialize the function
    interval(seconds=0.1)(do_a_print)

    await asyncio.sleep(0.2)
    assert "do_a_print" in sciop.scheduler.main._TO_SCHEDULE
    assert len(_eventlines(capsys)) == 0

    # starting the scheduler should pick up the task
    start_scheduler()
    await asyncio.sleep(0.25)

    events = _eventlines(capsys)
    assert len(events) == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_date_decorator(capsys, clean_scheduler):
    """
    Date decorators should let one declare a job before the scheduler exists,
    and then run it afterwards
    """
    assert get_scheduler() is None

    # can't use as a decorator because apscheduler needs to be able to serialize the function
    date(datetime.now(UTC) + timedelta(seconds=0.2))(do_a_print)

    await asyncio.sleep(0.1)
    assert "do_a_print" in sciop.scheduler.main._TO_SCHEDULE
    assert len(_eventlines(capsys)) == 0

    # starting the scheduler should pick up the task
    start_scheduler()
    await asyncio.sleep(0.2)

    events = _eventlines(capsys)
    assert len(events) == 1


@pytest.mark.asyncio
async def test_disabled_decorator(capsys, clean_scheduler):
    """
    Decorators should be able to be toggled by their enabled parameter
    so they can be configured :)
    """
    assert get_scheduler() is None
    # can't use as a decorator because apscheduler needs to be able to serialize the function
    interval(seconds=0.01, enabled=False)(do_a_print)

    await asyncio.sleep(0.1)
    assert "do_a_print" not in sciop.scheduler.main._TO_SCHEDULE
    assert len(_eventlines(capsys)) == 0

    # starting the scheduler should NOT pick up the task
    start_scheduler()
    await asyncio.sleep(0.1)

    events = _eventlines(capsys)
    assert len(events) == 0


def test_queue_job(capsys, clean_scheduler, set_config):
    """
    Queueing jobs should run them one at a time
    """

    set_config({"server.scheduler_mode": "rpc"})
    print("starting scheduler")
    queue(enabled=True, max_concurrent=1, job_name="sleepytime")(sleep_for_a_bit)
    # need to fork to share an event
    start_scheduler()
    time.sleep(0.1)
    # queue 3 of the same job, we should only run one at a time
    messages = ["a", "b", "c"]
    results = [queue_job("sleepytime", msg) for msg in messages]
    assert all([result["success"] for result in results])
    queued_jobs = get_queued_jobs("sleepytime")
    assert len(queued_jobs) == 3

    # Wait until at least 1 has finished.
    # multiple jobs *could* start here if the pool was larger, but they shouldn't
    # that's what we're testing lol
    client = get_scheduler()
    evt1 = client.await_event(EVENT_JOB_EXECUTED, 10)

    queued_jobs = get_queued_jobs("sleepytime")
    assert len(queued_jobs) == 2

    evt2 = client.await_event(EVENT_JOB_EXECUTED, 1)

    queued_jobs = get_queued_jobs("sleepytime")
    assert len(queued_jobs) == 1

    evt3 = client.await_event(EVENT_JOB_EXECUTED, 1)

    # since they ran in sequence, theoretically, even though pools are unordered,
    # the results should be ordered
    ordered_ids = [evt["job_id"] for evt in [evt1, evt2, evt3]]
    expected_order = [
        res["job"]["id"] for res in sorted(results, key=lambda x: x["job"]["args"][0])
    ]
    assert ordered_ids == expected_order


@pytest.mark.xfail(reason="write me plz")
def test_no_unauthed_rpc_access():
    raise NotImplementedError()
