SciOp
=====

collecting at-risk data in torrent rss feeds

# Running a SciOp Instance

These instructions are for executing the `sciop` tool.

*TODO: what does the sciop tool do and why would you want to run your own instance?*

## Installing Dependencies

Make a python virtual environment and activate it:

    python -m venv ~/.envs/sciop
    . ~/.envs/sciop/bin/activate

Make sure `pip` is reasonably new:

    pip install --upgrade pip

Install dependencies and then sciop itself in-place as an editable requirement:

    pip install -e .

## Running SciOp

Create a configuration starting from the sample:

    cp .env.sample .env
    $EDITOR .env

**NB: the `secret_key` field must be a securely-generated random hex value. This is specified in the template `.env` file.**

Run sciop:

    sciop

# Contributing

We use [`pdm`](https://pdm-project.org/latest/) to build and interact with the code in this repo for contributions. This workflow is slightly different than simply executing the tool.

## Setup Development Environment

`pdm` can be installed at the top level, without entering a virtual environment:

    pip install pdm

However, it is also possible to install `pdm` within an existing venv.

Then, `pdm` can install dependencies, implicitly creating a venv if not already within one:

    pdm install

## Testing Your Changes

To run the code within the worktree:

    pdm run start

To fix formatting and imports:

    pdm run format

To run lint:

    pdm run lint

To run automated testing:

    pdm run test

Changes can then be submitted as a pull request against this repository on Codeberg.

# Troubleshooting

## DB Migrations
We currently don't support database migrations, so old versions of the sqlite db can cause errors upon changes to the code. By default, the database is located at `./db.sqlite` wherever you invoke `sciop` from, so deleting the database should resolve any exceptions relating to missing columns and the like:

    rm -v ./db.sqlite

Note that we expect this to change soon to support real db migrations, which will make this workaround unnecessary.

# License
[EUPL v1.2](./LICENSE)


# Vendored Software

This project includes the following vendored software:

- [htmx](https://htmx.org/) - Zero-Clause BSD
- [form-json](https://github.com/xehrad/form-json/) - GPL 3.0
- [fastapi_rss](https://github.com/sbordeyne/fastapi_rss) - MIT