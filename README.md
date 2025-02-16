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

First, setup a virtual environment and ensure pip is up to date as described in [installing dependencies](#installing-dependencies), but *without* installing anything else besides pip itself yet:

    python -m venv ~/.envs/sciop
    . ~/.envs/sciop/bin/activate
    pip install --upgrade pip

To install `pdm`:

    pip install pdm

## Testing Your Changes

To run the code within the worktree:

    pdm run start

To fix formatting and imports:

    pdm run format

To run lint:

    pdm run lint

Changes can then be submitted as a pull request against this repository on Codeberg.

# Troubleshooting

## DB Migrations
We currently don't support database migrations, so old versions of the sqlite db can cause errors upon changes to the code. By default, the database is located at `./db.sqlite` wherever you invoke `sciop` from, so deleting the database should resolve any exceptions relating to missing columns and the like:

    rm -v ./db.sqlite

# License
[EUPL v1.2](./LICENSE)
