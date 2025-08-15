from __future__ import annotations

import multiprocessing as mp
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, TypeVar

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.base import BaseScheduler

from sciop.logging import init_logger
from sciop.scheduler.registry import Registry, ScheduledJob

if TYPE_CHECKING:
    from apscheduler.jobstores.base import BaseJobStore

_TScheduler = TypeVar("_TScheduler", bound=BaseScheduler)


class SchedulerProtocol(Protocol):
    """
    Abstract protocol class representing the methods that we use from an apscheduler Scheduler
    and that must be implemented by a proxy class.
    """

    add_job = BaseScheduler.add_job
    get_job = BaseScheduler.get_job
    remove_job = BaseScheduler.remove_job
    remove_all_jobs = BaseScheduler.remove_all_jobs
    shutdown = BaseScheduler.shutdown


class BaseSchedulerManager(ABC):
    """
    Base class for classes that manage an apscheduler instance.

    Schedulers should be singletons for a single sciop instance,
    rather than a scheduler per worker,
    so many of the public methods are classmethods since instantiation
    binds us into ugly module-level consts.
    """

    scheduler_created = mp.Semaphore(1)

    @classmethod
    def start(cls) -> None:
        should_start = cls.scheduler_created.acquire(False)
        if not should_start:
            return
        cls.start_scheduler()

    @classmethod
    def shutdown(cls) -> None:
        if cls.is_running():
            cls.shutdown_scheduler()
            cls.scheduler_created.release()

    @classmethod
    def add_registered_jobs(
        cls, scheduler: _TScheduler, scheduled_jobs: dict[str, ScheduledJob] | None = None
    ) -> _TScheduler:
        logger = init_logger("scheduler.manager")
        if scheduled_jobs is None:
            scheduled_jobs = {}
        for job_params in {**Registry.get_scheduled_jobs(), **scheduled_jobs}.values():
            if job_params.enabled:
                logger.debug("Adding registered job: %s", job_params)
                scheduler.add_job(
                    job_params.func,
                    job_params.trigger,
                    id=job_params.job_id,
                    replace_existing=True,
                    kwargs=job_params.job_kwargs,
                    **job_params.kwargs,
                )
                logger.debug("Added registered job: %s", job_params.job_id)
            elif (
                not job_params.enabled and (job := scheduler.get_job(job_params.job_id)) is not None
            ):
                logger.info(
                    "Found scheduled job %s, but %s is configured to be disabled. Unscheduling."
                )
                logger.debug("Prior job config: %s\nCurrent job config: %s", job, job_params)
                scheduler.remove_job(job_params.job_id)
        return scheduler

    @classmethod
    def make_jobstores(cls) -> dict[str, BaseJobStore]:
        from sciop.db import get_engine

        engine = get_engine()

        return {"default": SQLAlchemyJobStore(engine=engine)}

    @classmethod
    @abstractmethod
    def start_scheduler(cls) -> None:
        """
        Start the scheduler.

        Only allows a single scheduler (of any kind) to be started,
        and if one already has, returns silently.

        Subclasses should
        - schedule any jobs that are yet to be scheduled in the registry,
          as declared through decorators.
        - if applicable, create process pools for queued tasks.
        """

    @classmethod
    @abstractmethod
    def shutdown_scheduler(cls) -> None:
        """
        Stop the scheduler and release its resources.
        Should be idempotent over the shutdown process -
        if the scheduler is already stopped/stopping, do nothing.
        """

    @classmethod
    @abstractmethod
    def get_scheduler(cls) -> SchedulerProtocol | None:
        pass

    @classmethod
    @abstractmethod
    def is_running(cls) -> bool:
        """
        Stop the scheduler and release its resources.
        Should be idempotent over the shutdown process -
        if the scheduler is already stopped/stopping, do nothing.
        """
