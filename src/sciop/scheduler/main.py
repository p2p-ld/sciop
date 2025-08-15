from __future__ import annotations

from types import FunctionType
from typing import Any, Sequence
from xmlrpc.client import Fault

from apscheduler.job import Job

from sciop import get_config
from sciop.exceptions import ConfigException, SchedulerNotRunningError
from sciop.logging import init_logger
from sciop.scheduler.base import SchedulerProtocol
from sciop.scheduler.local import LocalSchedulerManager
from sciop.scheduler.rpc import QueueResult, RPCClientProtocol, RPCSchedulerManager


def get_manager() -> type[LocalSchedulerManager] | type[RPCSchedulerManager]:
    cfg = get_config()
    if cfg.server.scheduler_mode == "local":
        return LocalSchedulerManager
    elif cfg.server.scheduler_mode == "rpc":
        return RPCSchedulerManager
    else:
        raise ConfigException(f"No manager for scheduler mode {cfg.server.scheduler_mode}")


def get_scheduler() -> SchedulerProtocol | None:
    manager = get_manager()
    return manager.get_scheduler()


def start_scheduler(**kwargs: Any) -> None:
    manager = get_manager()
    return manager.start()


def started() -> bool:
    manager = get_manager()
    return manager.is_running()


def shutdown() -> None:
    manager = get_manager()
    manager.shutdown()


def remove_all_jobs() -> None:
    scheduler = get_scheduler()
    logger = init_logger("scheduler")
    if scheduler is not None:
        logger.debug("Clearing jobs")
        try:
            scheduler.remove_all_jobs("default")
        except (Fault, ConnectionRefusedError):
            logger.debug("RPC Connection refused - could not clear jobs")
        except Exception as e:
            logger.exception(f"Could not clear jobs: {e}")
    else:
        logger.warning("Scheduler has not been started, can't clear yet")


def add_job(func: FunctionType | str, *args: Any, **kwargs: Any) -> Job:
    scheduler = get_scheduler()
    if scheduler is None:
        raise SchedulerNotRunningError(f"Scheduler is not running! Can't add job {func}")
    return scheduler.add_job(func, *args, **kwargs)


def queue_job(
    job_name: str,
    args: Sequence[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> QueueResult:
    """
    Queue a job to be executed.

    Can only be run in RPC mode,
    (otherwise the other gunicorn/uvicorn workers would not be able to communicate with
    the scheduler, since it must only be spawned in one worker)

    The service must already be registered with :func:`.queue` ,
    since functions generally can't be serialized over xml-rpc.

    All args/kwargs must be serializable with xml-rpc,
    typically this means they must be base python types.

    Note that queued jobs exit apscheduler's jobstore immediately and are only stored in memory,
    as job queues are not intended for persistence between runs.
    As a result, apscheduler's usual `get_jobs` and etc. methods don't work.
    Queued jobs can be accessed with :func:`.get_queued_jobs`
    and cancelled with :func:`.cancel_queued_job`.
    """
    cfg = get_config()
    if cfg.server.scheduler_mode != "rpc":
        return QueueResult(success=False, message="Queued jobs only work in RPC mode")
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    scheduler: RPCClientProtocol = get_scheduler()

    return scheduler.queue_job(job_name, args, kwargs)
