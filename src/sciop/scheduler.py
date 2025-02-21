from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.memory import MemoryJobStore

from sqlmodel import Session
from sqlalchemy.engine.base import Engine

from sciop.db import get_engine

# buddy, they don't even let _me_ download the car

engine = get_engine()


def create_scheduler(engine: Engine = engine) -> AsyncIOScheduler:
    jobstores = {"default": MemoryJobStore(), "sql": SQLAlchemyJobStore(engine=engine)}
    scheduler = AsyncIOScheduler(jobstores=jobstores)
    print("HELLO I AM CREATE SCHEDULER, I AM CALLED BUT ONCE")
    print(scheduler)
    return scheduler


scheduler = create_scheduler()


def get_scheduler() -> AsyncIOScheduler:
    return scheduler
