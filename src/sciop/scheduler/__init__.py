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

from sciop.scheduler.decorator import cron, date, interval, queue
from sciop.scheduler.main import (
    add_job,
    get_manager,
    get_scheduler,
    queue_job,
    remove_all_jobs,
    shutdown,
    start_scheduler,
    started,
)

__all__ = [
    "add_job",
    "get_manager",
    "get_scheduler",
    "queue_job",
    "remove_all_jobs",
    "shutdown",
    "start_scheduler",
    "started",
    "cron",
    "date",
    "interval",
    "queue",
]
