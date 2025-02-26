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
def add_job(func: Callable, trigger: str | BaseTrigger = 'interval', scheduler_kwargs = {}, *args, **kwargs) -> Job:
    # A little convenience parsing for those who do not want to use the explicit scheduler_kwargs
    # I'm not married to this; if we think it's a hassle, we can just get rid of it.
    del_key = []
    for kwarg in kwargs.keys():
        if kwarg not in func.__annotations__.keys():
            scheduler_kwargs[kwarg] = kwargs[kwarg]
            del_key.append(kwarg)
    # You can't mutate while you're iterating!
    for key in del_key:
        del(kwargs[key])
    logger.debug(f"""Adding job to scheduler: 
                   job:            {func}
                   job args:       {args}
                   job kwargs:     {kwargs}
                   trigger:        {trigger}
                   trigger kwargs: {scheduler_kwargs}
    """)
    return scheduler.add_job(func, trigger=trigger, kwargs=kwargs, **scheduler_kwargs)

def print_job(msg: str, num: int = 0) -> None:
    logger.info(f"PRINT: {num}:{msg}")
