from apscheduler.schedulers.asyncio import AsyncIOScheduler

from sciop.logging import init_logger
from sciop.scheduler.base import BaseSchedulerManager


class LocalSchedulerManager(BaseSchedulerManager):
    scheduler: AsyncIOScheduler | None = None

    @classmethod
    def start_scheduler(cls) -> None:
        logger = init_logger("scheduler.manager.local")
        if cls.scheduler is not None and cls.scheduler.running:
            logger.warning("Scheduler is already running!")
            return

        cls.scheduler = AsyncIOScheduler(jobstores=cls.make_jobstores())
        cls.scheduler.start()
        logger.debug("Local scheduler started")
        cls.scheduler = cls.add_registered_jobs(cls.scheduler)

    @classmethod
    def shutdown_scheduler(cls) -> None:
        logger = init_logger("scheduler.manager.local")
        logger.info("Shutting down scheduler")
        if cls.is_running():
            cls.scheduler.shutdown()
            cls.scheduler = None
            logger.info("Scheduler shutdown complete")
        else:
            logger.info("Scheduler is not running, not shutting down.")

    @classmethod
    def get_scheduler(cls) -> AsyncIOScheduler:
        return cls.scheduler

    @classmethod
    def is_running(cls) -> bool:
        return cls.scheduler is not None and cls.scheduler.running
