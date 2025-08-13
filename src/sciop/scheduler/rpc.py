from __future__ import annotations

import base64
import contextlib
import hashlib
import multiprocessing as mp
import secrets
import signal
import threading
from datetime import datetime
from types import FrameType
from typing import Any, NotRequired, TypedDict, cast
from xmlrpc.client import Fault, ServerProxy
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from apscheduler.events import EVENT_JOB_EXECUTED, JobEvent, JobExecutionEvent, JobSubmissionEvent
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.job import Job
from apscheduler.schedulers import SchedulerNotRunningError
from apscheduler.schedulers.background import BackgroundScheduler

from sciop import get_config
from sciop.logging import init_logger
from sciop.scheduler.base import BaseSchedulerManager, SchedulerProtocol
from sciop.scheduler.registry import QueuedJob

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


class RPCSchedulerManager(BaseSchedulerManager):
    """
    Run a scheduler + sub-pools of queue workers in a separate process with an xml-rpc proxy
    """

    rpc_process: mp.Process | None = None

    @classmethod
    def get_scheduler(cls) -> SchedulerProtocol | None:
        try:
            client = _start_rpc_client()
            client = cast("_BackgroundSchedulerProxy", client)
        except Fault:
            return None
        return client

    @classmethod
    def shutdown_scheduler(cls) -> None:
        logger = init_logger("scheduler.manager.rpc")
        if cls.rpc_process is not None and cls.rpc_process.is_alive():
            scheduler = cls.get_scheduler()
            with contextlib.suppress(ConnectionRefusedError):
                # scheduler would already be shut down if we refused connection
                scheduler.shutdown()
            cls.rpc_process.terminate()
            cls.rpc_process.join(timeout=5)
            if cls.rpc_process.is_alive():
                logger.info(
                    "Scheduler RPC process could not be terminated cleanly, killing process"
                )
                cls.rpc_process.kill()


class _BackgroundSchedulerProxy(BackgroundScheduler):
    """Typing-only subclass that represents the methods available to the xml-rpc client"""

    def queue_job(self, job_name: str, *args: Any, **kwargs: Any) -> _QueueResult: ...

    def get_queued_jobs(self, queue_name: str) -> dict[str, MarshallableJob]: ...

    def await_event(
        self, event: int, timeout: int | None = None
    ) -> JobEvent | JobSubmissionEvent | JobExecutionEvent: ...


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


def _add_queue_executors(
    scheduler: BackgroundScheduler,
    queue_params: dict[str, QueuedJob],
) -> BackgroundScheduler:
    for exec_name, exec_params in queue_params.items():
        if not exec_params.enabled:
            continue
        scheduler.add_executor(
            ProcessPoolExecutor(max_workers=exec_params.max_concurrent), alias=exec_name
        )
        logger.debug("Added executor %s", exec_name)
    return scheduler


def _create_rpc_server(start_event: mp.Event, queue_params: dict[str, QueuedJob]) -> None:
    global logger
    # import here to trigger job definition

    # replace the global logger in this process, in case it is used by any other functions
    config = get_config()
    logger = init_logger("scheduling.rpc")
    logger.debug("got queue params: %s", queue_params)
    scheduler: BackgroundScheduler = create_scheduler()
    scheduler = _add_queue_executors(scheduler, queue_params)
    queued_jobs: dict[str, dict] = {}
    # if get_config().services.clear_jobs:
    #     remove_all_jobs()

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

            # --------------------------------------------------
            # THESE ARE JUST FOR DEVELOPMENT PURPOSES AND SHOULD BE REMOVED BEFORE MERGING
            # --------------------------------------------------
            def _signal_shutdown(*args, **kwargs) -> None:
                logger.debug("shutdown - signal")
                _shutdown(*args, **kwargs)

            def _atexit_shutdown(*args, **kwargs) -> None:
                logger.debug("shutdown - atexit")
                _shutdown(*args, **kwargs)

            def _finally_shutdown(*args, **kwargs) -> None:
                logger.debug("shutdown - finally shutdown")
                _shutdown(*args, **kwargs)

            scheduler.start()
            scheduler.add_listener(_job_complete_callback, EVENT_JOB_EXECUTED)
            _start_pending_jobs(scheduler)
            server.register_instance(scheduler)
            server.register_function(_queue_job, "queue_job")
            server.register_function(_get_queued_jobs, "get_queued_jobs")
            server.register_function(_shutdown, "shutdown_rpc")
            server.register_function(_await_event, "await_event")

            # signal.signal(signal.SIGTERM, _signal_shutdown)
            # atexit.register(_atexit_shutdown)

            start_event.set()
            logger.debug("Starting RPC Server")
            server.serve_forever()
            logger.debug("Quitting RPC Server")
            # sys.exit(0)
    finally:
        start_event.set()
        _finally_shutdown(sig=signal.SIGTERM, frame=None)


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
