# `config`

!!! info "See Also"

    For viewing and setting config values on a sciop instance,
    see the [CLI docs for sciop config](../running/cli.md#sciop-config)

Config uses [`pydantic-settings`](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

Config values can be set (in order of priority where earlier sources override later sources) 

- in environment variables
- in a `.env` file in the cwd
- in a `sciop.yaml` file in the cwd (preferred)

## Syntax

### yaml

yaml syntax is straightforward, a 1:1 mapping between the config file and the Config object
 
```yaml
env: dev
paths:
  db: ./db.sqlite
logs:
  level: INFO
```

### .env files and env vars

- Keys are prefixed with `SCIOP_`
- Nested models are delimited with `__`

For example, for this:

```python
class PathConfig(BaseSettings):
    db: Path

class LogConfig(BaseSettings):
    level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR']
    
class Config(BaseSettings):
    env: Literal["dev", "prod", "test"]
    logs: LogConfig = LogConfig()
    paths: PathConfig = PathConfig()
```

One can specify a `.env` file like

```env
SCIOP_ENV="dev"
SCIOP_PATHS__DB=./db.sqlite
SCIOP_LOGS__LEVEL=INFO
```

## Usage

Within `sciop`, the `Config` behaves like a singleton, loaded once per run.
- You should not re-instantiate it, and instead use the [get_config][sciop.config.get_config] accessor.
- Using `get_config` is cheap, and it should be treated effectively as a constant for perf concerns.
- Once loaded, the config should *never* be mutated.
- You should *avoid* storing references to or copies of the config,
  just use `get_config()` -- 
  **except** within small, temporary scopes like within a function body.

Config is available in templates as the global variable `config`.
Plugins and template overrides should *never* print the full config,
the [SecretStr][pydantic.SecretStr] types prevent the secret key and root password
from being printed accidentally, but the contents of the config should be considered sensitive
as they contain information that could aid abuse of an instance.

## Main

::: sciop.config.get_config
    options:
        heading_level: 3

::: sciop.config.Config

## Sub-configs

### Database

::: sciop.config.DBConfig
    options:
        heading_level: 4
        parameter_headings: false

### Feeds

::: sciop.config.FeedConfig
    options:
        heading_level: 4
        parameter_headings: false

### Instance

Configuration for the user-facing parts of an instance, like its rules, name, etc.

::: sciop.config.InstanceConfig
    options:
        heading_level: 4
        parameter_headings: false

::: sciop.config.InstanceRule
    options:
        heading_level: 4
        parameter_headings: false

### Logs

::: sciop.config.LogConfig
    options:
        heading_level: 4
        parameter_headings: false

### Paths

All paths used within sciop.

::: sciop.config.PathConfig
    options:
        heading_level: 4
        parameter_headings: false

### Server

The backend configuration for how and from where content is served from.

Distinct from instance config since this is more technical config about the *act of serving*
of files, as opposed to the colloquial use of "server" to refer to a federated instance
(which is configured in [InstanceConfig][sciop.config.InstanceConfig]).

::: sciop.config.ServerConfig
    options:
        heading_level: 4
        parameter_headings: false

::: sciop.config.server.CSPConfig
    options:
        heading_level: 4

## Services

Background services.

!!! note "Terminology Note"

    At the moment we use "service" and "job" more or less interchangeably.
    But if there is a pattern, a "service" is the function itself, 
    and the "job" is its configured form or a single run of a service.
    e.g. "A server's configured services are its jobs."

::: sciop.config.ServicesConfig
    options:
        heading_level: 3

::: sciop.config.JobConfig
    options:
        heading_level: 3

### Tracker Scraping

::: sciop.config.ScrapeConfig
    options:
        heading_level: 4

::: sciop.config.ScrapeErrorBackoffs
    options:
        heading_level: 4

### Instance Stats

::: sciop.config.StatsConfig
    options:
        heading_level: 4