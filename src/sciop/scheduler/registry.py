"""
Module that is treated as a class
"""

from __future__ import annotations

from threading import Lock
from types import FunctionType
from typing import Any, Callable, Literal, ParamSpec, TypeVar

from pydantic import BaseModel, Field

from sciop.config import get_config
from sciop.logging import init_logger

P = ParamSpec("P")
T = TypeVar("T")


class ScheduledJob(BaseModel):
    """
    Container for job parameterization before scheduler started
    """

    func: Callable | str
    job_id: str
    trigger: Literal["cron", "date", "interval"]
    job_kwargs: dict[str, Any] = Field(default_factory=dict)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class QueuedJob(BaseModel):
    """
    Container for queued job parameterization,
    mapping strings to functions for calling over rpc with {func}`.queue_job`
    """

    func: Callable | str
    job_name: str
    """
    ID to use for job within apscheduler,
    and also when queueing the job.
    """
    queue_name: str
    """
    Name of the queue to run the job in.
    Currently always the same as job_name,
    but left as a point of future expansion.
    """
    max_concurrent: int = 1
    """Maximum number of concurrent instances of this job"""
    enabled: bool = True


class Registry:
    """
    Registry singleton class that holds job descriptions defined in `jobs.py`
    for storing parameterizations in the brief window of time after import
    but before the scheduler is started
    (and in case the scheduler crashes).

    The sqlalchemy jobstore should handle job persistence between runs,
    but it doesn't handle the kind of statically-defined jobs we have here,
    so we need to wrap the process a bit.

    Not intended for instance instantiation,
    purposefully mutable class vars for use with accessor methods.

    Mostly a class to avoid having a spray of module-level consts
    """

    _scheduled_jobs = {}
    _queued_jobs = {}
    _lock = Lock()

    @classmethod
    def register_scheduled_job(
        cls,
        func: Callable,
        trigger: Literal["cron", "date", "interval"],
        enabled: bool = True,
        job_kwargs: dict | None = None,
        **kwargs: Any,
    ) -> ScheduledJob:
        job_id = func.__name__
        job_params = ScheduledJob(
            func=func,
            job_id=job_id,
            trigger=trigger,
            job_kwargs=job_kwargs,
            kwargs=kwargs,
            enabled=enabled,
        )
        with cls._lock:
            if job_id in cls._scheduled_jobs and cls._scheduled_jobs[job_id] != job_params:
                logger = init_logger("scheduler.registry")
                logger.info(
                    "Existing job parameterization found for job_id %s and was not equal, "
                    "replacing",
                    job_id,
                )
                logger.debug(
                    "Previous parameterization: %s\nNew parameterization: %s",
                    cls._scheduled_jobs[job_id],
                    job_params,
                )
            cls._scheduled_jobs[job_id] = job_params
        return job_params

    @classmethod
    def register_queued_job(
        cls,
        func: FunctionType,
        job_name: str | None = None,
        enabled: bool = True,
        max_concurrent: int = 1,
    ) -> QueuedJob:

        logger = init_logger("scheduler.registry")
        cfg = get_config()

        if job_name is None:
            job_name = func.__name__
        func_name = f"{func.__module__}:{func.__name__}"

        if cfg.server.scheduler_mode != "rpc" and enabled:
            logger.warning(
                "Incompatible scheduler: Queued job %s (%s) is enabled, "
                "but scheduler_mode %s does not support queued jobs. "
                "Queued jobs will be ignored. "
                "Explicitly set services.%s.enabled = False "
                'or set server.scheduler_mode = "rpc" '
                "to silence this warning.",
                job_name,
                func_name,
                cfg.server.scheduler_mode,
                job_name,
            )

        job_params = QueuedJob(
            job_name=job_name,
            queue_name=job_name,
            func=func_name,
            max_concurrent=max_concurrent,
            enabled=enabled,
        )
        with cls._lock:
            if job_name in cls._scheduled_jobs and cls._scheduled_jobs[job_name] != job_params:
                logger.info(
                    "Existing job parameterization found for job_id %s and was not equal, "
                    "replacing",
                    job_name,
                )
                logger.debug(
                    "Previous parameterization: %s\nNew parameterization: %s",
                    cls._scheduled_jobs[job_name],
                    job_params,
                )

            cls._queued_jobs[job_name] = job_params
        return job_params

    @classmethod
    def get_scheduled_jobs(cls) -> dict[str, ScheduledJob]:
        # import to ensure they are defined and added to the registry
        import sciop.jobs  # noqa: F401

        with cls._lock:
            return cls._scheduled_jobs.copy()

    @classmethod
    def get_queued_jobs(cls) -> dict[str, QueuedJob]:
        with cls._lock:
            return cls._queued_jobs.copy()
