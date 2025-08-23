from __future__ import annotations

import asyncio
import atexit
import base64
import contextlib
import hashlib
import multiprocessing as mp
import secrets
import signal
import threading
from datetime import datetime
from typing import Any, NotRequired, TypedDict, cast
from xmlrpc.client import Fault, ServerProxy
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from apscheduler.events import JobEvent, JobExecutionEvent, JobSubmissionEvent
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.job import Job
from apscheduler.jobstores.base import BaseJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers import SchedulerNotRunningError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler

from sciop import get_config
from sciop.logging import init_logger
from sciop.scheduler.base import BaseSchedulerManager, SchedulerProtocol
from sciop.scheduler.registry import QueuedJob, Registry, ScheduledJob


class RPCClientProtocol(SchedulerProtocol):
    def queue_job(self, job_name: str, *args: Any, **kwargs: Any) -> QueueResult: ...

    def await_event(
        self, event: int, timeout: int | None = None
    ) -> JobEvent | JobSubmissionEvent | JobExecutionEvent: ...


class MarshallableJob(TypedDict):
    id: str
    func: str
    executor: str
    args: list
    kwargs: dict
    name: str | None
    next_run_time: datetime


class QueueResult(TypedDict):
    success: bool
    message: NotRequired[str]
    job: NotRequired[MarshallableJob]


class RPCSchedulerManager(BaseSchedulerManager):
    """
    Run a scheduler + sub-pools of queue workers in a separate process with an xml-rpc proxy
    """

    rpc_process: mp.Process | None = None
    start_event = mp.Event()
    rpc_pass = secrets.token_urlsafe(32)
    """
    single-use password created at module level so forked processes have it.
    use to authenticate localhost-only rpc even if the port is exposed publicly.
    assuming we don't accidentally print this in an API response,
    the security model is basically the same as the secret key used to generate auth tokens,
    where if an attacker has access to the python interpreter or can access program memory,
    we're probably already pwned.
    """

    @classmethod
    def start_scheduler(cls, block: bool = False) -> None:
        logger = init_logger("scheduler.manager.rpc")
        logger.debug("Starting RPC scheduler")
        cls.start_event.clear()
        cls.rpc_process = mp.Process(
            target=RPCSchedulerServer.start,
            args=(
                cls.start_event,
                cls.rpc_pass,
                Registry.get_scheduled_jobs(),
                Registry.get_queued_jobs(),
            ),
        )
        cls.rpc_process.start()
        if block:
            was_started = cls.start_event.wait(10)
            if not was_started:
                logger.exception(
                    "RPC server was not finished starting by the time the startup timer expired, "
                    "Scheduler is not running!"
                )
                cls.rpc_process.kill()

    @classmethod
    def get_scheduler(cls) -> RPCClientProtocol | None:
        try:
            cls.start_event.wait(5)
            config = get_config()
            client = ServerProxy(
                f"http://sciop:{cls.rpc_pass}@127.0.0.1:{config.server.scheduler_rpc_port}",
                allow_none=True,
            )
            client = cast(RPCClientProtocol, client)
        except Fault:
            return None
        return client

    @classmethod
    def shutdown_scheduler(cls) -> None:
        # only try and do this from the spawning worker
        if cls.rpc_process is None:
            return
        logger = init_logger("scheduler.manager.rpc")
        logger.debug("Shutting down scheduler")

        scheduler = cls.get_scheduler()
        with contextlib.suppress(ConnectionRefusedError):
            # scheduler would already be shut down if we refused connection
            scheduler.shutdown()

        cls.rpc_process.join(1)
        if not cls.rpc_process.is_alive():
            return

        cls.rpc_process.terminate()
        cls.rpc_process.join(timeout=5)
        if cls.rpc_process.is_alive():
            logger.info("Scheduler RPC process could not be terminated cleanly, killing process")
            cls.rpc_process.kill()
        cls.rpc_process.close()
        cls.rpc_process = None

    @classmethod
    def is_running(cls) -> bool:
        try:
            scheduler = cls.get_scheduler()
            return scheduler is not None
        except Exception:
            return False

    @classmethod
    def make_jobstores(cls) -> dict[str, BaseJobStore]:
        from sciop.db import _make_engine

        engine = _make_engine()

        return {"default": SQLAlchemyJobStore(engine=engine)}


class AuthenticatingXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    """
    Request handler that checks for basic HTTP auth when serving requests

    References:
        copied from:
        https://idle.nprescott.com/2023/basic-auth-with-pythons-xmlrpc-server.html
    """

    rpc_pass: str = None

    def do_POST(self) -> None:  # noqa: N802
        if not (cred := self.headers.get("Authorization")):
            self._reject_auth()
            self.wfile.write(b"no auth header received")
        elif cred == "Basic " + base64.b64encode(f"sciop:{self.rpc_pass}".encode()).decode():
            super().do_POST()
        else:
            self._reject_auth()

    def _reject_auth(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", "Basic")
        self.send_header("Content-type", "text/html")
        self.end_headers()
        logger = init_logger("scheduler.rpc.server")
        logger.info("Rejected connection with invalid auth")


class RPCSchedulerServer:
    """
    Scheduler that runs in a separate process and is controlled over xml-rpc

    This class organizes the rpc methods and manages the scheduler state,
    and should not be interacted with directly elsewhere in the program -
    use the rpc client from the `RPCSchedulerManager.get_scheduler` method.
    """

    def __init__(
        self,
        start_event: mp.Event,
        rpc_pass: str,
        scheduled_jobs: dict[str, ScheduledJob],
        queued_jobs: dict[str, QueuedJob],
    ):
        self.start_event = start_event
        self.rpc_pass = rpc_pass
        self.scheduled_jobs = scheduled_jobs
        self.queued_jobs = queued_jobs
        self.logger = init_logger("scheduler.rpc.server")
        self.scheduler: BackgroundScheduler | None = None
        self.quitting = False

    @classmethod
    def start(
        cls,
        start_event: mp.Event,
        rpc_pass: str,
        scheduled_jobs: dict[str, ScheduledJob],
        queued_jobs: dict[str, QueuedJob],
    ) -> None:
        """
        Create and run the rpc server

        Intended to be the target of a multiprocessing.Process
        """
        instance = cls(start_event, rpc_pass, scheduled_jobs, queued_jobs)
        instance.run()

    def run(self) -> None:
        """
        Main loop: create the scheduler, rpc server, and serve it until stopped
        """
        from sciop.db import clear_globals

        clear_globals()
        self.scheduler = self.create_scheduler()
        try:
            with self.create_server(self.scheduler) as server:
                self.start_event.set()
                self.logger.debug("RPC Server started")
                while not self.quitting:
                    server.handle_request()
        except KeyboardInterrupt:
            pass
        finally:
            self.logger.debug("Shutting down RPC server")
            self.start_event.set()
            with contextlib.suppress(SchedulerNotRunningError):
                self.logger.debug("Shutting down background scheduler")
                self.scheduler.shutdown()
                self.scheduler = None
                self.logger.debug("Background scheduler shut down")
            self.logger.debug("RPC server shut down")

    def create_scheduler(self) -> AsyncIOScheduler:
        """
        Create and start the scheduler, adding job stores and executors
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        scheduler = AsyncIOScheduler(
            event_loop=loop,
            jobstores=RPCSchedulerManager.make_jobstores(),
            logger=init_logger("scheduler.background"),
        )
        for queue_name, queue_params in {
            **Registry.get_queued_jobs(),
            **self.queued_jobs,
        }.items():
            if not queue_params.enabled:
                self.logger.debug("Queued job %s disabled, not creating executors", queue_name)
                continue
            scheduler.add_executor(
                ProcessPoolExecutor(max_workers=queue_params.max_concurrent), alias=queue_name
            )
            self.logger.debug("Added queue executor %s", queue_name)

        scheduler.start()
        self.logger.debug("Scheduler started")

        scheduler = RPCSchedulerManager.add_registered_jobs(scheduler, self.scheduled_jobs)

        return scheduler

    @contextlib.contextmanager
    def create_server(self, scheduler: AsyncIOScheduler) -> SimpleXMLRPCServer:
        config = get_config()
        self.logger.debug("Starting RPC Server")
        AuthenticatingXMLRPCRequestHandler.rpc_pass = self.rpc_pass
        with SimpleXMLRPCServer(
            ("127.0.0.1", config.server.scheduler_rpc_port),
            requestHandler=AuthenticatingXMLRPCRequestHandler,
            allow_none=True,
            use_builtin_types=True,
            logRequests=False,
        ) as server:
            server.register_instance(scheduler)
            server.register_function(self.add_job, "add_job")
            server.register_function(self.queue_job, "queue_job")
            server.register_function(self.await_event, "await_event")
            server.register_function(self.shutdown, "shutdown")
            atexit.register(self.shutdown)
            signal.signal(signal.SIGTERM, lambda sig, frame: self.shutdown)
            # signal.signal(signal.SIGKILL, lambda sig, frame: self.shutdown)
            signal.signal(signal.SIGHUP, lambda sig, frame: self.shutdown)
            yield server

    def shutdown(self, signum: int = None, frame: Any = None) -> None:
        self.quitting = True

    def add_job(
        self, func: str, trigger: Any = None, args: Any = None, kwargs: Any = None, id: Any = None
    ) -> MarshallableJob:
        job = self.scheduler.add_job(func, trigger, args=args, kwargs=kwargs, id=id)
        return _marshall_job(job)

    def queue_job(
        self, job_name: str, args: list | None = None, kwargs: dict | None = None
    ) -> QueueResult:
        self.logger.debug(
            "Received request to queue %s; args: %s; kwargs: %s", job_name, args, kwargs
        )
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        queue_params = Registry.get_queued_jobs()
        params = self.queued_jobs.get(job_name, queue_params.get(job_name, None))
        if params is None:
            self.logger.warning(
                "Queue not parameterized before starting rpc server with @queue decorator"
            )
            return QueueResult(success=False, message=f"job name {job_name} not found")
        if not params.enabled:
            self.logger.debug("Queue %s not enabled", job_name)
            return QueueResult(success=False, message=f"job {job_name} disabled")

        job_id = hashlib.blake2b(
            str({"job_name": job_name, "args": args, "kwargs": kwargs}).encode()
        ).hexdigest()

        job = self.scheduler.add_job(
            func=params.func,
            id=job_id,
            args=args,
            kwargs=kwargs,
            misfire_grace_time=None,
            executor=params.queue_name,
        )
        marshallable = _marshall_job(job)
        self.logger.debug("Queued job: job: %s, args: %s, kwargs: %s", params.func, args, kwargs)
        return QueueResult(success=True, job=marshallable)

    def await_event(
        self, event: int, timeout: int | None = None
    ) -> JobEvent | JobSubmissionEvent | JobExecutionEvent:
        """
        Mostly for testing - pause execution until an event is received.

        Please don't put this in perf-sensitive code like api endpoints, that is bad to do.
        """

        evt = threading.Event()
        evt.clear()
        result = None

        def _cb(event: Any) -> None:
            nonlocal result
            result = event
            evt.set()

        self.scheduler.add_listener(_cb, event)
        evt.wait(timeout)
        self.scheduler.remove_listener(_cb)
        return result


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
