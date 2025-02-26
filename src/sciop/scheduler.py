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
from sciop.logging import init_logger

# buddy, they don't even let _me_ download the car

logger = init_logger('scheduling')

engine = get_engine()

def create_scheduler(engine: Engine = engine) -> AsyncIOScheduler:
    logger.debug(f"Using SQL engine for scheduler: {engine}")
    jobstores = {"default": MemoryJobStore(), "sql": SQLAlchemyJobStore(engine=engine)}
    logger.debug(f"Initializing AsyncIOScheduler w/ jobstores: {jobstores}")
    scheduler = AsyncIOScheduler(jobstores=jobstores)
    return scheduler


scheduler = create_scheduler()


def get_scheduler() -> AsyncIOScheduler:
    return scheduler

def start_scheduler() -> None:
    scheduler.start()

# I don't love it until I can find where the aliases are, but
# https://apscheduler.readthedocs.io/en/latest/modules/schedulers/base.html
# some string values are allowed, others are probably not.  I wish I could 
def add_job(func: Callable, trigger: str | BaseTrigger = 'interval', *args, **kwargs) -> Job:
    func_kwargs = {}
    # we do our best to parse out the function kwargs, but no guarantee.
    for param in func.__annotations__.keys():
        if param in kwargs.keys():
            func_kwargs[param] = kwargs.pop(param)
    logger.debug(f"""Adding job to scheduler: 
                   job:            {func}
                   job kwargs:     {func_kwargs}
                   trigger:        {trigger}
                   trigger args:   {args}
                   trigger kwargs: {kwargs}
    """)
    return scheduler.add_job(func, trigger=trigger, kwargs=func_kwargs, *args, **kwargs)

def print_job(msg: str, num: int = 0) -> None:
    logger.info(f"PRINT: {num}:{msg}")
