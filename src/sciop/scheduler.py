import asyncio
import atexit
import base64
import multiprocessing as mp
import secrets
import signal
import sys
import threading
from collections import deque
from datetime import UTC, datetime, timedelta, tzinfo
from functools import wraps
from multiprocessing import Semaphore
from types import FrameType, FunctionType
from typing import (
    Any,
    Callable,
    Coroutine,
    Literal,
    Optional,
    ParamSpec,
    Sequence,
    TypeVar,
    cast,
)
from xmlrpc.client import ServerProxy
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.executors.base import run_coroutine_job, run_job
from apscheduler.job import Job
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.util import iscoroutinefunction_partial
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
_RPC_PASS = secrets.token_urlsafe(32)
"""
single-use password created at module level so forked processes have it.
use to authenticate localhost-only rpc even if the port is exposed publicly.
assuming we don't accidentally print this in an API response,
the security model is basically the same as the secret key used to generate auth tokens,
where if an attacker has access to the python interpreter or can access program memory,
we're probably already pwned.
"""
_RPC_PROCESS: mp.Process | None = None


P = ParamSpec("P")
T = TypeVar("T")


class AuthenticatingXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    """
    Request handler that checks for basic HTTP auth when serving requests

    References:
        copied from:
        https://idle.nprescott.com/2023/basic-auth-with-pythons-xmlrpc-server.html
    """

    def do_POST(self) -> None:  # noqa: N802
        if not (cred := self.headers.get("Authorization")):
            self._reject_auth()
            self.wfile.write(b"no auth header received")
        elif cred == "Basic " + base64.b64encode(f"sciop:{_RPC_PASS}".encode()).decode():
            super().do_POST()
        else:
            self._reject_auth()

    def _reject_auth(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", "Basic")
        self.send_header("Content-type", "text/html")
        self.end_headers()


def _scheduler_rpc_server(start_event: mp.Event):
    config = get_config()
    logger = init_logger("scheduling.rpc")
    scheduler = create_scheduler()
    if get_config().services.clear_jobs:
        remove_all_jobs()

    loop = asyncio.get_event_loop()
    scheduler._eventloop = loop
    try:
        with SimpleXMLRPCServer(
            ("localhost", config.server.scheduler_rpc_port),
            requestHandler=SimpleXMLRPCRequestHandler,
        ) as server:

            scheduler.start()
            _start_pending_jobs()
            server.register_instance(scheduler)

            def _shutdown(sig: int, frame: FrameType | None) -> None:
                scheduler.shutdown()
                server.shutdown()

            signal.signal(signal.SIGTERM, _shutdown)
            atexit.register(_shutdown)
            start_event.set()
            logger.debug("Starting RPC Server")
            loop.run_in_executor(None, server.serve_forever)
            loop.run_forever()
            logger.debug("Quitting RPC Server")
            _shutdown(signal.SIGTERM, None)
            sys.exit(0)
    finally:
        loop.close()


def _start_scheduler_rpc_server() -> mp.Process:
    global _RPC_PROCESS
    start_event = mp.Event()
    start_event.clear()
    process = mp.Process(target=_scheduler_rpc_server, args=(start_event,))
    process.start()
    start_event.wait()
    _RPC_PROCESS = process
    return process


def _start_rpc_client() -> ServerProxy:
    config = get_config()
    proxy = ServerProxy(f"http://sciop:{_RPC_PASS}@localhost:{config.server.scheduler_rpc_port}")
    return proxy


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
    config = get_config()
    if config.server.scheduler_mode == "rpc":
        return _start_rpc_client()
    else:
        return scheduler


def _start_local_scheduler() -> None:
    global scheduler
    if scheduler is None:
        scheduler = create_scheduler()
    else:
        raise RuntimeError("Scheduler already started")

    if get_config().services.clear_jobs:
        remove_all_jobs()
    scheduler.start()
    logger.debug("Scheduler started")

    _start_pending_jobs()
    logger.debug("Pending jobs started")


def start_scheduler() -> None:
    global scheduler
    # prevent multiple schedulers from being spawned in multiple workers.
    # Use the --preload flag in gunicorn (see deployment docs)
    logger.debug("Starting scheduler")
    config = get_config()
    should_create = _SCHEDULER_CREATED.acquire(False)
    if not should_create:
        return
    elif config.server.scheduler_mode == "rpc":
        _start_scheduler_rpc_server()
    else:
        _start_local_scheduler()


def started() -> bool:
    global scheduler
    return scheduler is not None


def shutdown() -> None:
    global scheduler, _REGISTRY, _SCHEDULER_CREATED, _RPC_PROCESS
    logger.debug("Shutting down scheduler")
    if scheduler is not None:
        scheduler.shutdown()
    scheduler = None
    if _RPC_PROCESS is not None:
        _RPC_PROCESS.terminate()
        _RPC_PROCESS.join(timeout=5)
        if _RPC_PROCESS.is_alive():
            logger.info("Scheduler RPC process could not be terminated cleanly, killing process")
            _RPC_PROCESS.kill()
    _SCHEDULER_CREATED.release()
    logger.debug("Scheduler shut down")


def remove_all_jobs() -> None:
    global scheduler
    if scheduler is not None:
        logger.debug("Clearing jobs")
        try:
            scheduler.remove_all_jobs("default")
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


# --------------------------------------------------
# Job Queues
# --------------------------------------------------


class AsyncIOQueueExecutor(AsyncIOExecutor):
    """
    Runs a limited number of jobs in a named queue.
    APScheduler can't seem to do this out of the box,
    where the `max_instances` keyword doesn't really work
    to control a group of the same kind of job with different arguments,
    as we need here.

    When a job is submitted, if there are no slots remaining
    (determined by a semaphore), then hold the job in a queue.
    When a job completes, if there are any jobs in the queue, start them.
    """

    def __init__(self, max_jobs: int = 1):
        super().__init__()
        self.max_jobs = max_jobs

    def start(self, scheduler: AsyncIOScheduler, alias: str) -> None:
        super().start(scheduler, alias)
        self._init_private()

    def _do_submit_job(self, job: Job, run_times: list[datetime]) -> None:
        def callback(f: asyncio.Future) -> None:
            self._pending_futures.discard(f)
            try:
                events = f.result()
            except BaseException:
                self._run_job_error(job.id, *sys.exc_info()[1:])
            else:
                self._run_job_success(job.id, events)
            finally:
                next_job = None
                with self._lock:
                    self._semaphore.release()
                    if len(self._job_queue) > 0:
                        next_job = self._job_queue.popleft()
                        self._logger.debug("Running job from queue: %s", next_job[0])
                if next_job is not None:
                    self._do_submit_job(*next_job)

        # try to acquire semaphore. if we can't queue the job.
        self._logger.info("acquiring lock in submission")
        with self._lock:
            can_run = self._semaphore.acquire(blocking=False)
            if not can_run:
                self._job_queue.append((job, run_times))
                self._logger.debug("No slots remaining, queueing job to run later: %s", job)
                return
        self._logger.info("running queued job on submission")

        if iscoroutinefunction_partial(job.func):
            coro = run_coroutine_job(job, job._jobstore_alias, run_times, self._logger.name)
            f = self._eventloop.create_task(coro)
        else:
            f = self._eventloop.run_in_executor(
                None, run_job, job, job._jobstore_alias, run_times, self._logger.name
            )

        f.add_done_callback(callback)
        self._pending_futures.add(f)

    def _init_private(self) -> None:
        # Use threading sync objects rather than asyncio since all the queueing happens in sync land
        # Shouldn't need to use multiprocessing either, since calls from other processes
        # are proxied through the manager
        self._job_queue: deque[tuple[Job, list[datetime]]] = deque()
        self._lock = threading.RLock()
        self._semaphore = threading.BoundedSemaphore(self.max_jobs)

    def get_queued_jobs(self) -> list[tuple[Job, list[datetime]]]:
        with self._lock:
            queue = list(self._job_queue.copy())
        return queue

    def cancel_queued_job(self, job: str | Job) -> bool:
        """
        Cancel a queued job, either by the job's ID or by passing the job object

        Returns:
            ``True`` if successful, ``False`` otherwise.
        """
        with self._lock:
            found_job = None
            for queued_job in self._job_queue:
                if isinstance(job, Job) and queued_job[0] is job:
                    found_job = queued_job
                elif isinstance(job, str) and queued_job[0].id == job:
                    found_job = queued_job

                if found_job is not None:
                    self._job_queue.remove(queued_job)
                    return True

        return False


def queue_job(
    queue_name: str,
    func: FunctionType | Callable[[...], Coroutine],
    max_jobs: int = 1,
    args: Sequence[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> Job:
    """
    Queue a job to be executed.

    Only `max_jobs` of jobs with matching `queue_name` are able to run at once,
    all others after that are queued to run as each job finishes.

    `max_jobs` is only used the *first* time that a job is queued in a given queue.
    `max_jobs` cannot be modified once a queue is created.

    Note that queued jobs exit apscheduler's jobstore immediately and are only stored in memory,
    as job queues are not intended for persistence between runs.
    As a result, apscheduler's usual `get_jobs` and etc. methods don't work.
    Queued jobs can be accessed with :func:`.get_queued_jobs`
    and cancelled with :func:`.cancel_queued_job`.
    """

    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}
    scheduler = get_scheduler()
    if scheduler is None:
        raise RuntimeError("Scheduler has not been started!")
    try:
        logger.debug("Adding executor to scheduler: %s", queue_name)
        scheduler.add_executor(AsyncIOQueueExecutor(max_jobs=max_jobs), queue_name)
    except ValueError:
        logger.debug("Executor %s already exists", queue_name)

    job = scheduler.add_job(
        func,
        args=args,
        kwargs=kwargs,
        misfire_grace_time=None,
        executor=queue_name,
    )
    logger.debug("Queued job: job: %s, args: %s, kwargs: %s", func, args, kwargs)
    return job


def _get_queue_executor(queue_name: str) -> AsyncIOQueueExecutor:
    scheduler = get_scheduler()
    if scheduler is None:
        raise RuntimeError("Scheduler has not been started!")

    # raises KeyError if none found
    executor = scheduler._lookup_executor(queue_name)
    if not isinstance(executor, AsyncIOQueueExecutor):
        raise ValueError(f"Executor {queue_name} is not a queue executor")
    return executor


def list_queue_names() -> list[str]:
    """
    List the names of any job queues that exist
    """
    scheduler = get_scheduler()
    if scheduler is None:
        raise RuntimeError("Scheduler has not been started!")
    queue_names = [
        name for name, q in scheduler._executors.items() if isinstance(q, AsyncIOQueueExecutor)
    ]
    return queue_names


def get_queued_jobs(queue_name: str) -> list[tuple[Job, list[datetime]]]:
    """
    Get all jobs in a given queue.
    """
    executor = _get_queue_executor(queue_name)
    return executor.get_queued_jobs()


def cancel_queued_job(queue_name: str, job: Job | str) -> bool:
    """
    Cancel a queued job, either by passing the job object or its id.

    Returns:
        ``True`` if successfully removed, ``False`` if not found.
    """
    executor = _get_queue_executor(queue_name)
    return executor.cancel_queued_job(job)
