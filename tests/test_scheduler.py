import asyncio
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xmlrpc.client import ProtocolError, ServerProxy

import pytest
from apscheduler.events import EVENT_JOB_EXECUTED

from sciop.config import get_config
from sciop.logging import init_logger
from sciop.scheduler import (
    add_job,
    date,
    get_scheduler,
    interval,
    queue,
    queue_job,
    start_scheduler,
)
from sciop.scheduler.rpc import RPCClientProtocol
from sciop.testing.scheduler import write_a_file, write_a_file_sleepy

_EVENTS = 0


def do_a_print():
    """https://www.youtube.com/shorts/qG1LG1gADog"""
    print(f"EVENT: {datetime.now().isoformat()}")


def sleep_for_a_bit(arg: str, tmp_dir: Path):
    logger = init_logger("sleep")
    logger.warning(arg)
    with open(tmp_dir / arg, "w") as f:
        f.write(arg)
    time.sleep(1)


def _loglines(capsys) -> list[str]:
    stdout = capsys.readouterr().out
    lines = stdout.splitlines()
    return lines


def _eventlines(capsys) -> list[str]:
    lines = _loglines(capsys)
    return [line for line in lines if "EVENT" in line]


def _n_events(tmp_path) -> list[Path]:
    return len(list(tmp_path.glob("EVENT*")))


@pytest.fixture(params=["rpc", "local"])
def scheduler_type(request, set_config) -> str:
    set_config({"server.scheduler_mode": request.param})
    return request.param


async def test_add_job(scheduler_type, clean_scheduler, tmp_path):
    """
    do a single job
    """
    start_scheduler(block=True)
    add_job(
        "sciop.testing.scheduler:write_a_file",
        None,
        [
            str(tmp_path),
        ],
    )
    await asyncio.sleep(0.1)
    assert _n_events(tmp_path) == 1


@pytest.mark.asyncio
async def test_interval_decorator(scheduler_type, clean_scheduler, tmp_path):
    """
    Interval decorators should let one declare a job before the scheduler exists,
    and then run it afterwards
    """
    assert get_scheduler() is None
    # can't use as a decorator because apscheduler needs to be able to serialize the function
    interval(seconds=0.1, job_kwargs={"tmp_path": str(tmp_path)})(write_a_file)

    await asyncio.sleep(0.2)
    assert _n_events(tmp_path) == 0

    # starting the scheduler should pick up the task
    start_scheduler()
    await asyncio.sleep(0.25)

    assert _n_events(tmp_path) == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_date_decorator(scheduler_type, clean_scheduler, tmp_path):
    """
    Date decorators should let one declare a job before the scheduler exists,
    and then run it afterwards
    """
    assert get_scheduler() is None
    assert _n_events(tmp_path) == 0

    # can't use as a decorator because apscheduler needs to be able to serialize the function
    date(
        datetime.now(UTC) + timedelta(seconds=0.2),
        job_kwargs={"tmp_path": str(tmp_path)},
        misfire_grace_time=None,
    )(write_a_file)
    start_scheduler()

    # starting the scheduler should pick up the task
    start_scheduler()
    await asyncio.sleep(0.2)

    assert _n_events(tmp_path) == 1


@pytest.mark.asyncio
async def test_disabled_decorator(scheduler_type, tmp_path, clean_scheduler):
    """
    Decorators should be able to be toggled by their enabled parameter
    so they can be configured :)
    """
    assert get_scheduler() is None
    # can't use as a decorator because apscheduler needs to be able to serialize the function
    interval(seconds=0.01, enabled=False, job_kwargs={"tmp_path": str(tmp_path)})(write_a_file)

    await asyncio.sleep(0.1)
    assert _n_events(tmp_path) == 0

    # starting the scheduler should NOT pick up the task
    start_scheduler()
    await asyncio.sleep(0.1)

    assert _n_events(tmp_path) == 0


def test_queue_job(capsys, clean_scheduler, set_config, tmp_path):
    """
    Queueing jobs should run them one at a time
    """

    set_config({"server.scheduler_mode": "rpc"})
    print("starting scheduler")
    sleep_dir = tmp_path / "sleepy"
    sleep_dir.mkdir(exist_ok=True)
    queue(enabled=True, max_concurrent=1, job_name="sleepytime")(write_a_file_sleepy)
    start_scheduler()
    time.sleep(0.1)
    # queue 3 of the same job, we should only run one at a time
    messages = ["a", "b", "c"]
    results = [queue_job("sleepytime", [str(sleep_dir), msg]) for msg in messages]
    assert all([result["success"] for result in results])
    assert len(list(sleep_dir.iterdir())) == 0

    # Wait until at least 1 has finished.
    # multiple jobs *could* start here if the pool was larger, but they shouldn't
    # that's what we're testing lol
    client: RPCClientProtocol = get_scheduler()
    evt1 = client.await_event(EVENT_JOB_EXECUTED, 10)

    assert len(list(sleep_dir.iterdir())) == 1

    evt2 = client.await_event(EVENT_JOB_EXECUTED, 1)

    assert len(list(sleep_dir.iterdir())) == 2

    evt3 = client.await_event(EVENT_JOB_EXECUTED, 1)

    # since they ran in sequence, theoretically, even though pools are unordered,
    # the results should be ordered
    ordered_ids = [evt["job_id"] for evt in [evt1, evt2, evt3]]
    expected_order = [
        res["job"]["id"] for res in sorted(results, key=lambda x: x["job"]["args"][0])
    ]
    assert ordered_ids == expected_order


def test_no_unauthed_rpc_access(clean_scheduler, set_config):
    set_config({"server.scheduler_mode": "rpc"})
    start_scheduler(block=True)
    config = get_config()
    client = ServerProxy(f"http://127.0.0.1:{config.server.scheduler_rpc_port}")
    # calling incorrectly doesn't matter, we should fail
    with pytest.raises(ProtocolError) as e:
        client.add_job()
    assert e.value.errcode == 401
