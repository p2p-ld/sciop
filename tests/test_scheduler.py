from datetime import datetime, timedelta
from time import sleep

import pytest

from sciop.scheduler import add_job, date, interval


def do_a_print():
    """https://www.youtube.com/shorts/qG1LG1gADog"""
    print(f"EVENT: {datetime.now().isoformat()}")


def test_add_job(client_lifespan, capsys):
    """
    do a single job
    """
    add_job(do_a_print)
    sleep(0.5)
    stdout = capsys.readouterr().out
    lines = stdout.splitlines()
    assert any(["Adding job" in line for line in lines])
    assert any(["EVENT" in line for line in lines])


def test_interval(client_lifespan, capsys):
    """
    Do a job at an interval
    """
    interval(do_a_print, seconds=0.2)
    sleep(0.7)
    stdout = capsys.readouterr().out
    lines = stdout.splitlines()
    events = [line for line in lines if "EVENT" in line]
    assert len(events) == 3


def test_date(client_lifespan, capsys):
    """
    Do a job at a time
    """
    todo = datetime.now() + timedelta(seconds=0.5)
    date(do_a_print, run_date=todo)
    sleep(0.7)
    stdout = capsys.readouterr().out
    lines = stdout.splitlines()
    events = [line for line in lines if "EVENT" in line]
    assert len(events) == 1
    pass


@pytest.mark.skip(
    reason="there isn't really a good way to test cron tasks, so skipping until we figure it out"
)
def test_cron(client_lifespan, capsys):
    """
    Do a job with cron syntax
    """
    pass
