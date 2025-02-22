from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.job import Job
from apscheduler.triggers.base import BaseTrigger
from typing import Callable
from enum import StrEnum

from sqlmodel import Session
from sqlalchemy.engine.base import Engine

from sciop.db import get_engine

# buddy, they don't even let _me_ download the car

engine = get_engine()

class TriggerAlias(StrEnum):
    Date = 'date'
    Interval = 'interval'
    Cron = 'cron'
    CalendarInterval = 'calendarinterval'


def create_scheduler(engine: Engine = engine) -> AsyncIOScheduler:
    jobstores = {"default": MemoryJobStore(), "sql": SQLAlchemyJobStore(engine=engine)}
    scheduler = AsyncIOScheduler(jobstores=jobstores)
    print("HELLO I AM CREATE SCHEDULER, I AM CALLED BUT ONCE")
    print(scheduler)
    return scheduler


scheduler = create_scheduler()


def get_scheduler() -> AsyncIOScheduler:
    return scheduler

def start_scheduler() -> None:
    scheduler.start()

# I don't love it until I can find where the aliases are, but
# https://apscheduler.readthedocs.io/en/latest/modules/schedulers/base.html
# some string values are allowed, others are probably not.  I wish I could 
def add_job(func: Callable, trigger: str | TriggerAlias | BaseTrigger = 'interval', *args, **kwargs) -> Job:
    print(args, kwargs)
    return scheduler.add_job(func, 'interval', seconds=1, args=args, kwargs=kwargs)

def print_job(msg: str, num: int = 0) -> None:
    print(f"TALES FROM SCIOP: {num}:{msg}")
