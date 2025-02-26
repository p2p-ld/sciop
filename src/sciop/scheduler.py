from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.job import Job
from apscheduler.triggers.base import BaseTrigger
from typing import Callable
from functools import wraps

from sqlmodel import Session
from sqlalchemy.engine.base import Engine

from sciop.db import get_engine
from sciop.logging import init_logger

# buddy, they don't even let _me_ download the car

logger = init_logger('scheduling')

engine = get_engine()

def create_scheduler(engine: Engine = engine) -> AsyncIOScheduler:
    logger.debug(f"Using SQL engine for scheduler: {engine}")
    jobstores = {"default": SQLAlchemyJobStore(engine=engine)}
    logger.debug(f"Initializing AsyncIOScheduler w/ jobstores: {jobstores}")
    scheduler = AsyncIOScheduler(jobstores=jobstores)
    return scheduler


scheduler = create_scheduler()

def get_scheduler() -> AsyncIOScheduler:
    return scheduler

def start_scheduler() -> None:
    scheduler.start()

def _split_job_kwargs(func, **kwargs):
    # A little convenience parsing for those who do not want to use the explicit scheduler_kwargs
    # I'm not married to this; if we think it's a hassle, we can just get rid of it.
    del_key = []
    scheduler_kwargs = {}
    for kwarg in kwargs.keys():
        if kwarg not in func.__annotations__.keys():
            scheduler_kwargs[kwarg] = kwargs[kwarg]
            del_key.append(kwarg)
    # You can't mutate while you're iterating!
    for key in del_key:
        del(kwargs[key])
    return kwargs, scheduler_kwargs

def _add_job(func: Callable, trigger: str | BaseTrigger = 'interval', scheduler_kwargs = {}, job_args = [], job_kwargs = {}) -> Job:
    logger.debug(f"""Adding job to scheduler: 
                   job:            {func}
                   job args:       {job_args}
                   job kwargs:     {job_kwargs}
                   trigger:        {trigger}
                   trigger kwargs: {scheduler_kwargs}
    """)
    return scheduler.add_job(func, trigger=trigger, args=job_args, kwargs=job_kwargs, **scheduler_kwargs)

# https://apscheduler.readthedocs.io/en/latest/modules/schedulers/base.html
def add_job(func: Callable, trigger: str | BaseTrigger = 'interval', scheduler_kwargs = {}, *args, **kwargs) -> Job:
    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(func, trigger=trigger, scheduler_kwargs=scheduler_kwargs, job_args=args, job_kwargs=job_kwargs)

def interval(func: Callable, *args, **kwargs) -> Job:
    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(func, trigger='interval', scheduler_kwargs=scheduler_kwargs, job_args=args, job_kwargs=job_kwargs)

def date(func: Callable, *args, **kwargs) -> Job:
    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(func, trigger='date', scheduler_kwargs=scheduler_kwargs, job_args=args, job_kwargs=job_kwargs)

def cron(func: Callable, *args, **kwargs) -> Job:
    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(func, trigger='cron', scheduler_kwargs=scheduler_kwargs, job_args=args, job_kwargs=job_kwargs)

def do_not_run(func: Callable, *args, **kwargs) -> Job:
    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    import sys
    sys.exit(0)
    heavenly_args = (func, *args)
    _add_job(do_not_run, trigger='interval', scheduler_kwargs=scheduler_kwargs, job_args=heavenly_args, job_kwargs=job_kwargs)

    return _add_job(func, trigger='interval', scheduler_kwargs=scheduler_kwargs, job_args=args, job_kwargs=job_kwargs)


def print_job(msg: str, num: int = 0) -> None:
    logger.info(f"PRINT: {num} : {msg}")

def remove_all_jobs():
    scheduler.remove_all_jobs()

remove_all_jobs()
