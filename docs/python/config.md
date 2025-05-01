# `config`

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
db: ./db.sqlite
logs:
  dir: ./logs
  level: INFO
```

### .env files and env vars

- Keys are prefixed with `SCIOP_`
- Nested models are delimited with `__`

For example, for this:

```python
class LogConfig(BaseSettings):
    dir: Path
    level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR']
    
class Config(BaseSettings):
    db: Path
    logs: LogConfig = LogConfig()
```

One can specify a `.env` file like

```env
SCIOP_DB=./db.sqlite
SCIOP_LOGS__DIR=./logs
SCIOP_LOGS__LEVEL=INFO
```

::: sciop.config.Config

## Sub-configs

::: sciop.config.InstanceConfig
    options:
        heading_level: 3
        parameter_headings: false

::: sciop.config.LogConfig
    options:
        heading_level: 3

::: sciop.config.CSPConfig
    options:
        heading_level: 3

## Job configs

::: sciop.config.JobConfig
    options:
        heading_level: 3

### Tracker Scraping

::: sciop.config.ScrapeErrorBackoffs
    options:
        heading_level: 4

::: sciop.config.ScrapeConfig
    options:
        heading_level: 4

### Instance Stats

::: sciop.config.StatsConfig
    options:
        heading_level: 4