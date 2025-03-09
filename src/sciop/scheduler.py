from types import FunctionType
from typing import Any, Callable, Optional, Sequence

from apscheduler.job import Job
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger
from sqlalchemy.engine.base import Engine

from sciop.db import get_engine
from sciop.logging import init_logger

# buddy, they don't even let _me_ download the car

logger = init_logger("scheduling")


def create_scheduler(engine: Optional[Engine] = None) -> AsyncIOScheduler:
    if engine is None:
        engine = get_engine()
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


def _split_job_kwargs(func: FunctionType, **kwargs: dict[str, Any]) -> tuple[dict, dict]:
    # A little convenience parsing for those who do not want to use the explicit scheduler_kwargs
    # I'm not married to this; if we think it's a hassle, we can just get rid of it.
    del_key = []
    scheduler_kwargs = {}
    for kwarg in kwargs:
        if kwarg not in func.__annotations__:
            scheduler_kwargs[kwarg] = kwargs[kwarg]
            del_key.append(kwarg)
    # You can't mutate while you're iterating!
    for key in del_key:
        del kwargs[key]
    return kwargs, scheduler_kwargs


def _add_job(
    func: Callable,
    trigger: str | BaseTrigger = "interval",
    scheduler_kwargs: Optional[dict] = None,
    job_args: Optional[Sequence] = None,
    job_kwargs: Optional[dict] = None,
) -> Job:
    if scheduler_kwargs is None:
        scheduler_kwargs = {}
    if job_args is None:
        job_args = []
    if job_kwargs is None:
        job_kwargs = {}

    logger.debug(
        f"""Adding job to scheduler: 
                   job:            {func}
                   job args:       {job_args}
                   job kwargs:     {job_kwargs}
                   trigger:        {trigger}
                   trigger kwargs: {scheduler_kwargs}
    """
    )
    return scheduler.add_job(
        func, trigger=trigger, args=job_args, kwargs=job_kwargs, **scheduler_kwargs
    )


# https://apscheduler.readthedocs.io/en/latest/modules/schedulers/base.html
def add_job(
    func: FunctionType,
    trigger: str | BaseTrigger = "interval",
    *args: Any,
    **kwargs: dict[str, Any],
) -> Job:

    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(
        func,
        trigger=trigger,
        scheduler_kwargs=scheduler_kwargs,
        job_args=args,
        job_kwargs=job_kwargs,
    )


def interval(func: Callable, *args: Any, **kwargs: dict[str, Any]) -> Job:
    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(
        func,
        trigger="interval",
        scheduler_kwargs=scheduler_kwargs,
        job_args=args,
        job_kwargs=job_kwargs,
    )


def date(func: Callable, *args: Any, **kwargs: dict[str, Any]) -> Job:
    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(
        func,
        trigger="date",
        scheduler_kwargs=scheduler_kwargs,
        job_args=args,
        job_kwargs=job_kwargs,
    )


def cron(func: Callable, *args: Any, **kwargs: dict[str, Any]) -> Job:
    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(
        func,
        trigger="cron",
        scheduler_kwargs=scheduler_kwargs,
        job_args=args,
        job_kwargs=job_kwargs,
    )


def print_job(msg: str, num: int = 0) -> None:
    logger.info(f"PRINT: {num} : {msg}")


def remove_all_jobs() -> None:
    scheduler.remove_all_jobs()
