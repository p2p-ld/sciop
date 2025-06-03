# Changelog

## 2025-06

### 2025-06-02

**Refactoring**

- [#431](https://codeberg.org/Safeguarding/sciop/pulls/431), [#411](https://codeberg.org/Safeguarding/sciop/issues/411) - 
  Create an `/api/v1/uploads` POST method for creating a new upload,
  and refactor the `/api/v1/datasets/{slug}/upload` methods to use it.
- [#431](https://codeberg.org/Safeguarding/sciop/pulls/431), [#430](https://codeberg.org/Safeguarding/sciop/issues/430) -
  Move `/api/v1/upload/torrent` to `/api/v1/torrents` because it's ridiculous to
  have both an `/upload` and an `/uploads` endpoint.


## 2025-05

### 2025-05-26.0

**Perf**

- [#401](https://codeberg.org/Safeguarding/sciop/pulls/401) ([@transorsmth](https://codeberg.org/transorsmth)) - 
  Add indices to `created_at` columns for Datasets, Uploads, and SiteStats for faster sort by queries,
  also add a `limit(1)` to the site stats to avoid loading all the stats at once

**Bugfix**

- [#403](https://codeberg.org/Safeguarding/sciop/pulls/403) - Run scheduler only once when launched with multiple workers,
  Add a `sciop generate gunicorn` template to standardize deployments.

### 2025-05-23.0

**Perf**

- [#397](https://codeberg.org/Safeguarding/sciop/pulls/397) ([@transorsmth](https://codeberg.org/transorsmth)) -
  Make the hit counter update as a delayed background task that doesn't slow down returning `index.html`

**Feature**

- [#398](https://codeberg.org/Safeguarding/sciop/pulls/398) ([@transorsmth](https://codeberg.org/transorsmth)) -
  Add configurable quote randomizer for homepage, see [`InstanceConfig.quotes`][sciop.config.instance.InstanceConfig.quotes]
  and [`InstanceQuote`][sciop.config.instance.InstanceQuote]

### 2025-05-21.0 - Start Changelog, Refactor Module-level items

- Changelog started, sorry about that.
- [#394](https://codeberg.org/Safeguarding/sciop/pulls/394) - Allow config to be instantiated with all defaults
- [#395](https://codeberg.org/Safeguarding/sciop/pulls/395) - rm module-level db engine, maker. cleanup resources in tests
- [#396](https://codeberg.org/Safeguarding/sciop/pulls/396) - Refactor config

We had been using a pattern of instantiating singleton objects at a module level at import time.

This is bad to do, it was mostly a matter of convenience.
These PRs start a process of converting those to getters/setters,
making these objects lazily-instantiated as well as possible to
work programmatically with, including monkeypatching, mutating, etc.

Most of these changes centered on config.

#### Allow Config with only defaults

Previously, one had to set `env`, `db`, and `secret_key` explicitly before running sciop.
This also included *importing* anything from sciop, which broke the ability to
use the cli to create an initial config. 

The config now fills in `env=dev` by default, which gives the default db path of `./db.dev.sqlite`,
and it generates a random `secret_key`.
Note that the `secret_key` will change on every run,
so it should be set explicitly even in `dev`.

#### Replace module-level db engine and maker

Replaced with `get_engine` and `get_maker` universally.

Also resolved some resource management issues that were causing hundreds of errors from unclosed dbs
to be raised during tests.

#### New config runtime features

- You can pass a custom config yaml file with `sciop start -c some-other-config.yaml` now.
- Configs (both default `sciop.yaml` in cwd and custom locations) auto-reload,
  checking every `config_watch_minutes` for changes - no more restarting prod to change a config variable!
  This does *not* necessarily work for *every* config variable - e.g. scheduled services
  read and consume their timing values at import time, but it *does* work with any variables
  that are dynamically accessed. Please raise an issue if there is some config value that isn't responding to changes.

#### Breaking - Refactor config

The Config object was split into more submodels and made into a subpackage.

The module-level `config` object was also converted into a [get_config][sciop.config.get_config]
function, which allows better control over config at runtime and avoids
needing to load and validate a config at import time.

This also allowed us to add a `sciop start -c some-other-config.yaml` cli option :)

Existing configs will need to be modified to use the new keys:

| Old                       | New                       |
|---------------------------|---------------------------|
| db                        | paths.db                  |
| template_dir              | paths.template_override   |
| logs.dir                  | paths.logs                |
| torrent_dir               | paths.torrents            |
| base_url                  | server.base_url           |
| public_url                | server.base_url           |
| host                      | server.host               |
| port                      | server.port               |
| csp                       | server.csp                |
| db_echo                   | db.echo                   |
| db_pool_size              | db.pool_size              |
| db_overflow_size          | db.overflow_size          |
| rss_feed_cache_delta      | feeds.cache_delta         |
| rss_feed_cache_clear_time | feeds.cache_clear_time    |
| clear_jobs                | services.clear_jobs       |
| tracker_scraping          | services.tracker_scraping |
| site_stats                | services.site_stats       |
| request_timing            | logs.request_timing       |

