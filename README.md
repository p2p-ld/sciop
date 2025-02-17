# SciOp

collecting at-risk data in torrent rss feeds

## Running SciOp

Make an environment and activate it:

    python -m venv ~/.envs/sciop
    . ~/.envs/sciop/bin/activate
    
Make sure `pip` is reasonably new

    pip install --upgrade pip

Install dependencies and install sciop in-place:

    pip install -e .

Create a configuration starting from the sample:

    cp .env.sample .env
    $EDITOR .env

Run sciop

    sciop


## Vendored Software

This project includes the following vendored software:

- [htmx](https://htmx.org/) - Zero-Clause BSD
- [form-json](https://github.com/xehrad/form-json/) - GPL 3.0
- [fastapi_rss](https://github.com/sbordeyne/fastapi_rss) - MIT