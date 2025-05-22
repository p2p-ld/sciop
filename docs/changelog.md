# Changelog

## 2025-05

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

#### Breaking - Refactor config

The Config object was split into more submodels and made into a subpackage.

The module-level `config` object was also converted into a [get_config][sciop.config.get_config]
function, which allows better control over config at runtime and avoids
needing to load and validate a config at import time.

This also allowed us to add a `sciop start -c some-other-config.yaml` cli option :)

Existing configs will need to be modified to use the new keys:

| Old | New |
| --- | --- |
