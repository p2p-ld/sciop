from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
from types import FunctionType
from typing import Any, Callable, ParamSpec, TypeVar

from sciop import get_config
from sciop.scheduler.registry import Registry

T = TypeVar("T")
P = ParamSpec("P")


def date(
    run_date: datetime, timezone: tzinfo = UTC, enabled: bool = True, **kwargs: Any
) -> Callable[P, Callable]:
    kwargs["run_date"] = run_date
    kwargs["timezone"] = timezone

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        job_params = Registry.register_scheduled_job(func, "date", enabled=enabled, **kwargs)
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
        job_params = Registry.register_scheduled_job(func, "cron", enabled=enabled, **kwargs)
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
    kwargs.update(outer_kwargs)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        job_params = Registry.register_scheduled_job(func, "date", enabled=enabled, **kwargs)
        return job_params.wrapped

    return decorator


def queue(
    enabled: bool = True, max_concurrent: int = 1, job_name: str | None = None
) -> Callable[[FunctionType], FunctionType]:
    """
    Registers a function as being a queueable job.

    Queue a job by calling {func}`.queue_job` like

    ```
    queue_job(job_id, **kwargs)
    ```

    Args:
        max_concurrent (int): Max number of instances of this job that may run concurrently
        enabled (bool): Enable this job queue!
        job_id (str): ID to use when queueing jobs and within apscheduler.
            If ``None`` , use name of function

    """
    global _QUEUE_PARAMS

    def decorator(func: FunctionType) -> FunctionType:
        nonlocal job_name

        Registry.register_queued_job(
            func, job_name=job_name, enabled=enabled, max_concurrent=max_concurrent
        )
        return func

    return decorator
