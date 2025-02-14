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
