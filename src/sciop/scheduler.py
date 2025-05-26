from datetime import UTC, datetime, timedelta, tzinfo
from functools import wraps
from multiprocessing import Semaphore
from types import FunctionType
from typing import Any, Callable, Literal, Optional, ParamSpec, Sequence, TypeVar, cast

from apscheduler.job import Job
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from pydantic import BaseModel, Field
from sqlalchemy.engine.base import Engine

from sciop.config import get_config
from sciop.db import get_engine
from sciop.logging import init_logger

# buddy, they don't even let _me_ download the car

logger = init_logger("scheduling")
scheduler: AsyncIOScheduler = None
_TO_SCHEDULE: dict[str, "_ScheduledJob"] = {}
"""Jobs declared before the scheduler is run"""
_JOB_PARAMS: dict[str, "_ScheduledJob"] = {}
"""All job parameterizations"""
_REGISTRY: dict[str, Job] = {}
"""All registered jobs"""
_SCHEDULER_CREATED = Semaphore(1)
"""Limit the creation of scheduler instances to one"""

P = ParamSpec("P")
T = TypeVar("T")


class _ScheduledJob(BaseModel):
    """
    Container for job parameterization before scheduler started
    """

    func: Callable
    wrapped: Optional[Callable] = None
    job_id: str
    trigger: Literal["cron", "date", "interval"]
    kwargs: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


def create_scheduler(engine: Optional[Engine] = None) -> AsyncIOScheduler:
    if engine is None:
        engine = get_engine()
    logger.debug(f"Using SQL engine for scheduler: {engine}")
    jobstores = {"default": SQLAlchemyJobStore(engine=engine)}
    logger.debug(f"Initializing AsyncIOScheduler w/ jobstores: {jobstores}")
    scheduler = AsyncIOScheduler(jobstores=jobstores)
    return scheduler


def get_scheduler() -> AsyncIOScheduler:
    global scheduler
    return scheduler


def start_scheduler() -> None:
    global scheduler
    # prevent multiple schedulers from being spawned in multiple workers.
    # Use the --preload flag in gunicorn (see deployment docs)
    should_create = _SCHEDULER_CREATED.acquire(False)
    if not should_create:
        return

    if scheduler is None:
        scheduler = create_scheduler()
    else:
        raise RuntimeError("Scheduler already started")

    if get_config().services.clear_jobs:
        remove_all_jobs()
    scheduler.start()

    _start_pending_jobs()


def started() -> bool:
    global scheduler
    return scheduler is not None


def shutdown() -> None:
    global scheduler, _REGISTRY
    if scheduler is not None:
        scheduler.shutdown()
    scheduler = None


def remove_all_jobs() -> None:
    global scheduler
    if scheduler is not None:
        logger.debug("Clearing jobs")
        try:
            scheduler.remove_all_jobs()
        except Exception as e:
            logger.exception(f"Could not clear jobs: {e}")
    else:
        logger.warning("Scheduler has not been started, can't clear yet")


# --------------------------------------------------
# Decorators
# --------------------------------------------------


def date(
    run_date: datetime, timezone: tzinfo = UTC, enabled: bool = True, **kwargs: Any
) -> Callable[P, Callable]:
    kwargs["run_date"] = run_date
    kwargs["timezone"] = timezone

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        job_params = _register_job(func, "date", enabled=enabled, **kwargs)
        job_params.wrapped = _wrap_job(func, job_params)
        _schedule_job(job_params)
        return job_params.wrapped

    return decorator


def cron(
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    week: int | None = None,
    hour: int | None = None,
    minute: int | None = None,
    second: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    timezone: tzinfo = UTC,
    jitter: int | None = None,
    enabled: bool = True,
    **kwargs: Any,
) -> Callable[P, T]:
    outer_kwargs = {**locals()}
    outer_kwargs = {
        k: v for k, v in outer_kwargs.items() if v is not None and k not in ("kwargs", "enabled")
    }
    kwargs.update(outer_kwargs)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        job_params = _register_job(func, "cron", enabled=enabled, **kwargs)
        job_params.wrapped = _wrap_job(func, job_params)
        _schedule_job(job_params)
        return job_params.wrapped

    return decorator


def interval(
    weeks: int | float = 0,
    days: int | float = 0,
    hours: int | float = 0,
    minutes: int | float = 0,
    seconds: int | float = 0,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    timezone: tzinfo = UTC,
    jitter: int | None = None,
    enabled: bool = True,
    **kwargs: Any,
) -> Callable[P, T]:
    """
    Declare an interval task with a decorator.

    If ``start_date`` is ``None`` , schedule the first run for 10s in the future
    """
    if start_date is None and get_config().env != "test":
        start_date = datetime.now(UTC) + timedelta(seconds=10)
    outer_kwargs = {**locals()}
    outer_kwargs = {
        k: v
        for k, v in outer_kwargs.items()
        if v is not None and v != 0 and k not in ("kwargs", "enabled")
    }

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        kwargs.update(outer_kwargs)
        job_params = _register_job(func, "interval", enabled=enabled, **kwargs)
        job_params.wrapped = _wrap_job(func, job_params)
        _schedule_job(job_params)
        return job_params.wrapped

    return decorator


def _log_job_start(job: _ScheduledJob) -> None:
    logger.info("Running job: %s", job.job_id)


def _log_job_end(job: _ScheduledJob) -> None:
    logger.info("Completed job: %s", job.job_id)


def _register_job(
    func: Callable,
    trigger: Literal["cron", "date", "interval"],
    enabled: bool = True,
    **kwargs: Any,
) -> _ScheduledJob:
    global _REGISTRY, _TO_SCHEDULE
    kwargs["id"] = func.__name__

    job_params = _ScheduledJob(
        func=func, job_id=func.__name__, trigger=trigger, kwargs=kwargs, enabled=enabled
    )
    if job_params.job_id in _JOB_PARAMS:
        logger.warning(f"A job with name {job_params.job_id} already exists, overwriting")
    _JOB_PARAMS[job_params.job_id] = job_params
    return job_params


def _wrap_job(func: Callable[P, T], params: _ScheduledJob) -> Callable[P, T]:
    @wraps(func)
    async def _wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        _log_job_start(params)
        val = await func(*args, **kwargs)
        _log_job_end(params)
        return val

    return _wrapped


def _schedule_job(params: _ScheduledJob) -> None:
    global _TO_SCHEDULE, _REGISTRY
    if not params.enabled:
        logger.info("Job %s is disabled - not scheduling", params.job_id)
        return

    if started():
        _REGISTRY[params.job_id] = add_job(
            cast(FunctionType, params.wrapped), params.trigger, **params.kwargs
        )
    else:
        _TO_SCHEDULE[params.job_id] = params


def _start_pending_jobs() -> None:
    global _TO_SCHEDULE, _REGISTRY
    for job_id, params in _TO_SCHEDULE.items():
        if not params.enabled:
            logger.debug(
                "Job %s is disabled but was in the _TO_SCHEDULE map, that shouldnt happen",
                params.job_id,
            )
            continue
        _REGISTRY[job_id] = add_job(
            cast(FunctionType, params.wrapped), params.trigger, **params.kwargs
        )
    _TO_SCHEDULE = {}


# --------------------------------------------------
# Functional form
# --------------------------------------------------


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

    if "id" in scheduler_kwargs and (job := scheduler.get_job(scheduler_kwargs["id"])) is not None:
        logger.debug("Job %s is already scheduled, set SCIOP_CLEAR_JOBS=true to clear")
        return job

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
    trigger: str | BaseTrigger | None = None,
    *args: Any,
    **kwargs: dict[str, Any],
) -> Job:
    if trigger is None:
        trigger = DateTrigger(run_date=datetime.now())

    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(
        func,
        trigger=trigger,
        scheduler_kwargs=scheduler_kwargs,
        job_args=args,
        job_kwargs=job_kwargs,
    )


def add_interval(func: FunctionType, *args: Any, **kwargs: Any) -> Job:
    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(
        func,
        trigger="interval",
        scheduler_kwargs=scheduler_kwargs,
        job_args=args,
        job_kwargs=job_kwargs,
    )


def add_date(func: FunctionType, *args: Any, **kwargs: Any) -> Job:
    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(
        func,
        trigger="date",
        scheduler_kwargs=scheduler_kwargs,
        job_args=args,
        job_kwargs=job_kwargs,
    )


def add_cron(func: FunctionType, *args: Any, **kwargs: Any) -> Job:
    trigger = CronTrigger.from_crontab(kwargs["crontab"]) if "crontab" in kwargs else "cron"

    job_kwargs, scheduler_kwargs = _split_job_kwargs(func, **kwargs)
    return _add_job(
        func,
        trigger=trigger,
        scheduler_kwargs=scheduler_kwargs,
        job_args=args,
        job_kwargs=job_kwargs,
    )
