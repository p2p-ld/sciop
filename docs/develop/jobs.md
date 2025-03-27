# Scheduled Jobs

Scheduled jobs have three components:

- [`jobs`](#jobs) - the top-level operation that defines when a job is executed by calling a `service`
- [`services`](#services) - the code for the job
- [`scheduler`](#scheduler) - the long-running process that executes jobs according to their scheduling configuration

## Jobs

The `jobs.py` file is intended as a shorthand index of available jobs.
Each top-level job in `jobs.py` should contain as little code as possible,
ideally just calling a single service function. 

Each job should have its own configuration in the `config` object
that allows it to be enabled/disabled and otherwise have its scheduling configured.

## Services

Services should be relatively self-contained,
such that disabling a service does not cause the site to become unusable.

Services should be `async` and make careful use of resources, such as limiting
the number of concurrent `async` calls with a `Semaphore` or otherwise.
Avoid long-running processes, and split jobs into small, atomic units when possible
so that failure of any part of them doesn't break the whole thing.

Services should not have side effects except for mutating the database.

Services should export a single function with no parameters up to `sciop.services` to be called from `jobs.py`

## Scheduler

The scheduler module wraps [APScheduler](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
with a handful of convenience methods. 
It is started and torn down with starlette's lifespan contextmanager methods. 

The scheduler uses the database as its job store, 
so jobs can be persisted in the case of server crashes,
though currently they are removed when the server is requested to do an orderly shutdown.