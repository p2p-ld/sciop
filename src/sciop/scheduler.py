"""
Background job structure.

Defines the decorators and backend runners for scheduled and queued jobs,
see {mod}`.jobs` for the instantiation of specific jobs & services.

## Overview

The scheduler is started in a separate process by the first worker process that reaches
a semaphore. On startup, it reads the configuration from any decorated job functions
and schedules them for execution.

In most cases, jobs are fire and forget, but in the case that one needs to interact with the
scheduler during runtime, we run an XML-RPC server accessible from {func}`.get_scheduler`

## Queued Jobs

APScheduler doesn't support queueing several of the same kind of job with different parameters
out of the box, so we use apscheduler in a slightly nonstandard way

- Rather than using `max_instances` , (which, as above, doesn't allow scheduling multiple jobs
  with the same id), we spawn a process pool executor per job queue, and the pool size
  controls concurrent execution. This may be changed in the future to accomodate
  shared queues for distinct but related jobs.
- ... in progress rn ...

"""

from __future__ import annotations

import atexit
import base64
import contextlib
import hashlib
import multiprocessing as mp
import secrets
import signal
import sys
import threading
from datetime import UTC, datetime, timedelta, tzinfo
from functools import wraps
from multiprocessing import Semaphore
from types import FrameType, FunctionType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    NotRequired,
    Optional,
    ParamSpec,
    Sequence,
    TypedDict,
    TypeVar,
    cast,
)
from xmlrpc.client import Fault, ServerProxy
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from apscheduler.events import (
    EVENT_JOB_EXECUTED,
    JobEvent,
    JobExecutionEvent,
    JobSubmissionEvent,
)
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.job import Job
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers import SchedulerNotRunningError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler
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
_TO_SCHEDULE: dict[str, _ScheduledJob] = {}
"""Jobs declared before the scheduler is run"""
_JOB_PARAMS: dict[str, _ScheduledJob] = {}
"""All job parameterizations"""
_QUEUE_PARAMS: dict[str, _QueuedJob] = {}
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

if TYPE_CHECKING:

    class _BackgroundSchedulerProxy(BackgroundScheduler):
        """Typing-only subclass that represents the methods available to the xml-rpc client"""

        def queue_job(self, job_name: str, *args: Any, **kwargs: Any) -> _QueueResult: ...

        def get_queued_jobs(self, queue_name: str) -> dict[str, MarshallableJob]: ...

        def await_event(
            self, event: int, timeout: int | None = None
        ) -> JobEvent | JobSubmissionEvent | JobExecutionEvent: ...


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


class _QueuedJob(BaseModel):
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


def create_scheduler(engine: Optional[Engine] = None) -> AsyncIOScheduler | BackgroundScheduler:
    global _QUEUE_PARAMS
    if engine is None:
        engine = get_engine()
    config = get_config()
    logger.debug(f"Using SQL engine for scheduler: {engine}")
    jobstores = {"default": SQLAlchemyJobStore(engine=engine)}

    mode = config.server.scheduler_mode
    scheduler_cls = BackgroundScheduler if mode == "rpc" else AsyncIOScheduler

    logger.debug(f"Initializing Scheduler in {mode} mode w/ jobstores: {jobstores}")
    scheduler = scheduler_cls(jobstores=jobstores)
    return scheduler


def _add_queue_executors(
    scheduler: AsyncIOScheduler | BackgroundScheduler,
    queue_params: dict[str, _QueuedJob],
) -> AsyncIOScheduler | BackgroundScheduler:
    for exec_name, exec_params in queue_params.items():
        if not exec_params.enabled:
            continue
        scheduler.add_executor(
            ProcessPoolExecutor(max_workers=exec_params.max_concurrent), alias=exec_name
        )
        logger.debug("Added executor %s", exec_name)
    return scheduler


def get_scheduler() -> AsyncIOScheduler | _BackgroundSchedulerProxy | None:
    global scheduler
    config = get_config()
    if config.server.scheduler_mode == "rpc":
        try:
            client = _start_rpc_client()
            client = cast("_BackgroundSchedulerProxy", client)
            return client
        except Fault:
            return None
    else:
        return scheduler


def start_scheduler(**kwargs: Any) -> None:
    global scheduler
    # prevent multiple schedulers from being spawned in multiple workers.
    # Use the --preload flag in gunicorn (see deployment docs)
    logger.debug("Starting scheduler")
    config = get_config()
    should_create = _SCHEDULER_CREATED.acquire(False)
    if not should_create:
        return
    elif config.server.scheduler_mode == "rpc":
        _start_rpc_server(**kwargs)
    else:
        _start_local_scheduler()


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


def started() -> bool:
    global scheduler
    return scheduler is not None


def shutdown() -> None:
    global scheduler, _REGISTRY, _SCHEDULER_CREATED, _RPC_PROCESS
    logger.debug("Shutting down scheduler")
    if scheduler is not None:
        scheduler.shutdown()
    scheduler = None
    if _RPC_PROCESS is not None and _RPC_PROCESS.is_alive():
        scheduler = get_scheduler()
        with contextlib.suppress(ConnectionRefusedError):
            # scheduler would already be shut down if we refused connection
            scheduler.shutdown()
        _RPC_PROCESS.terminate()
        _RPC_PROCESS.join(timeout=5)
        if _RPC_PROCESS.is_alive():
            logger.info("Scheduler RPC process could not be terminated cleanly, killing process")
            _RPC_PROCESS.kill()
    _SCHEDULER_CREATED.release()
    logger.debug("Scheduler shut down")


def remove_all_jobs() -> None:
    scheduler = get_scheduler()
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


def queue(
    enabled: bool = True, max_concurrent: int = 1, job_name: str | None = None
) -> Callable[P, Callable]:
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

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        nonlocal job_name
        if job_name is None:
            job_name = func.__name__
        _QUEUE_PARAMS[job_name] = _QueuedJob(
            job_name=job_name,
            queue_name=job_name,
            func=f"{func.__module__}:{func.__name__}",
            max_concurrent=max_concurrent,
            enabled=enabled,
        )
        logger.debug("added queue description for %s: %s", job_name, _QUEUE_PARAMS[job_name])
        return func

    return decorator


def queue_job(
    job_name: str,
    args: Sequence[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> _QueueResult:
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
    global _QUEUE_PARAMS, logger

    cfg = get_config()
    if cfg.server.scheduler_mode != "rpc":
        return _QueueResult(success=False, message="Queued jobs only work in RPC mode")
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    scheduler = get_scheduler()

    return scheduler.queue_job(job_name, *args, **kwargs)


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


class MarshallableJob(TypedDict):
    id: str
    func: str
    executor: str
    args: list
    kwargs: dict
    name: str | None
    next_run_time: datetime


class _QueueResult(TypedDict):
    success: bool
    message: NotRequired[str]
    job: NotRequired[MarshallableJob]


def _marshall_job(job: Job) -> MarshallableJob:
    state = job.__getstate__()
    return MarshallableJob(
        id=state["id"],
        func=state["func"],
        executor=state["executor"],
        args=state["args"],
        kwargs=state["kwargs"],
        name=state["name"],
        next_run_time=state["next_run_time"],
    )


def _create_rpc_server(start_event: mp.Event, queue_params: dict[str, _QueuedJob]) -> None:
    global logger
    # replace the global logger in this process, in case it is used by any other functions
    config = get_config()
    logger = init_logger("scheduling.rpc")
    logger.debug("got queue params: %s", queue_params)
    scheduler: BackgroundScheduler = create_scheduler()
    scheduler = _add_queue_executors(scheduler, queue_params)
    queued_jobs: dict[str, dict] = {}
    if get_config().services.clear_jobs:
        remove_all_jobs()

    def _job_complete_callback(event: JobExecutionEvent) -> None:
        """remove job from queued jobs map when completed"""
        nonlocal queued_jobs
        global logger
        logger.debug("Completed queued job %s", event.job_id)
        with contextlib.suppress(KeyError):
            del queued_jobs[event.job_id]

    def _await_event(
        event: int, timeout: int | None = None
    ) -> JobEvent | JobSubmissionEvent | JobExecutionEvent:
        evt = threading.Event()
        evt.clear()
        result = None

        def _cb(event: Any) -> None:
            nonlocal result
            result = event
            evt.set()

        scheduler.add_listener(_cb, event)
        evt.wait(timeout)
        return result

    def _get_queued_jobs(queue_name: str) -> dict[str, dict]:
        nonlocal queued_jobs
        return {
            job_name: job
            for job_name, job in queued_jobs.items()
            if job.get("executor") == queue_name
        }

    # define local in-process versions of functions
    def _queue_job(job_name: str, *args: Any, **kwargs: Any) -> _QueueResult:
        global logger
        nonlocal scheduler, queued_jobs
        logger.debug("Received request to queue %s; args: %s; kwargs: %s", job_name, args, kwargs)
        if job_name not in queue_params:
            logger.warning(
                "Queue not parameterized before starting rpc server with @queue decorator"
            )
            return _QueueResult(success=False, message=f"job name {job_name} not found")
        params = queue_params[job_name]
        if not params.enabled:
            logger.debug("Queue %s not enabled", job_name)
            return _QueueResult(success=False, message=f"job {job_name} disabled")

        job_id = hashlib.blake2b(
            str({"job_name": job_name, "args": args, "kwargs": kwargs}).encode()
        ).hexdigest()

        job = scheduler.add_job(
            func=params.func,
            id=job_id,
            args=args,
            kwargs=kwargs,
            misfire_grace_time=None,
            executor=params.queue_name,
        )
        marshallable = _marshall_job(job)
        queued_jobs[job_id] = marshallable
        logger.debug("Queued job: job: %s, args: %s, kwargs: %s", params.func, args, kwargs)
        return _QueueResult(success=True, job=marshallable)

    try:
        with SimpleXMLRPCServer(
            ("localhost", config.server.scheduler_rpc_port),
            requestHandler=SimpleXMLRPCRequestHandler,
            allow_none=True,
            use_builtin_types=True,
            logRequests=False,
        ) as server:

            def _shutdown(sig: int | None = None, frame: FrameType | None = None) -> None:
                logger.debug("Trying to shut down RPC server")
                with contextlib.suppress(SchedulerNotRunningError):
                    scheduler.shutdown()
                server.shutdown()

            scheduler.start()
            scheduler.add_listener(_job_complete_callback, EVENT_JOB_EXECUTED)
            # _start_pending_jobs()
            server.register_instance(scheduler)
            server.register_function(_queue_job, "queue_job")
            server.register_function(_get_queued_jobs, "get_queued_jobs")
            server.register_function(_shutdown, "shutdown_rpc")
            server.register_function(_await_event, "await_event")

            signal.signal(signal.SIGTERM, _shutdown)
            atexit.register(_shutdown)

            start_event.set()
            logger.debug("Starting RPC Server")
            server.serve_forever()
            logger.debug("Quitting RPC Server")
            sys.exit(0)
    finally:
        start_event.set()
        _shutdown(signal.SIGTERM, None)


def _start_rpc_server(ctx: mp.context.BaseContext | None = None) -> mp.Process:
    global _RPC_PROCESS, _QUEUE_PARAMS
    if ctx is None:
        ctx = mp
    start_event = ctx.Event()
    start_event.clear()
    process = ctx.Process(target=_create_rpc_server, args=(start_event, _QUEUE_PARAMS))
    process.start()
    was_started = start_event.wait(10)
    if not was_started:
        logger.exception(
            "RPC server was not finished starting by the time the timeout was reached!"
        )
        process.kill()
    _RPC_PROCESS = process
    return process


def _start_rpc_client() -> ServerProxy:
    config = get_config()
    proxy = ServerProxy(f"http://sciop:{_RPC_PASS}@localhost:{config.server.scheduler_rpc_port}")
    return proxy


def list_queue_names() -> list[str]:
    """
    List the names of any job queues that exist
    """
    global _QUEUE_PARAMS
    return sorted(list(_QUEUE_PARAMS.keys()))


def get_queued_jobs(queue_name: str) -> dict[str, MarshallableJob]:
    """
    Get all jobs in a given queue.

    .. todo::

        Track job execution events to distinguish queued vs. in-progress jobs.
    """
    cfg = get_config()
    if cfg.server.scheduler_mode != "rpc":
        raise RuntimeError("Queued jobs are only available in rpc mode")
    scheduler = get_scheduler()
    return scheduler.get_queued_jobs(queue_name)
