SciOp
=====

[ [`ｄｏｃｓ`](https://sciop.net/docs) ] [ [`ｓｏｕｒｃｅ`](https://codeberg.io/Safeguarding/sciop) ]

As a website and group of people: A distributed archive curated by distributed archivists
preserving public information to plug the memoryhole.

As software: An experimental (soon to be) federated bittorrent tracker.


# Running a SciOp Instance

**Please see full instructions in the [contributing docs](https://sciop.net/docs/develop/contributing/)**

## Installing

Clone the repository:

```shell
git clone https://codeberg.org/Safeguarding/sciop
cd sciop
```

### With pip

Make a python virtual environment and activate it:

    python -m venv ~/.envs/sciop
    . ~/.envs/sciop/bin/activate

Install dependencies and then sciop itself in-place as an editable requirement:

    pip install -e .

`sciop` is also available on [PyPI](https://pypi.org/project/sciop/),
though while we are in beta we do not regularly deploy versions there,
so installing from the repository is *strongly recommended.*

```shell
python -m pip install sciop
```

### With PDM

Install dependencies, automatically creating a virtual environment by default

    pdm install

## Configuration

All of the following commands can be run either with a venv or pdm install,
though only the venv version is shown. 
For PDM installs, just prepend `pdm run` like `pdm run sciop start` 

Create a default configuration:

```shell
# to see all config commands,
# sciop config --help

sciop config copy
```

Two fields *must* be set:
- `SCIOP_ENV`/`env`: one of `dev`, `test` or `prod`. 
  One should *only* make a sciop instance publicly available in `prod` mode.
  `dev` mode is for local development purposes, as is `test`.
  You must ensure that you do not re-use the same db between a `dev`/`test` and `prod`
  instance, e.g. if the `SCIOP_DB` location is explicitly set to something other than the defaults.
- `SCIOP_SECRET_KEY`/`secret_key`: must be a securely-generated random hex value.
  A key can be generated with `openssl rand -hex 32`.

When generated from the cli, `env` is set to `dev`, 
and `secret_key` is automatically generated.

## Run the dev sever

```shell
# see available CLI commands
# sciop --help

sciop start
```

# License
[EUPL v1.2](./LICENSE)

# Vendored Software

This project includes the following vendored software:

- [htmx](https://htmx.org/) - Zero-Clause BSD
- [form-json](https://github.com/xehrad/form-json/) - GPL 3.0
- [fastapi_rss](https://github.com/sbordeyne/fastapi_rss) - MIT
