# Debugging

## Database

### Echo Queries

When the database is doing unexpected things,
a decent first step is to take a look at the queries that are emitted to the database.

To echo db queries in the development server, set the `DB_ECHO` config param to `true`

In `.env` file:

```env
SCIOP_DB_ECHO=true
```

In env var

```shell
# with pdm
SCIOP_DB_ECHO=true pdm run start
# with venv
SCIO_DB_ECHO=true sciop start 
```

This is usually very noisy, 
so it's usually best to write a test that isolates the behavior in question.

Say we have written some test like this:

```python
def test_weird_db_thing(session):
    ds = Dataset(slug="test", publisher="test", description="test", tags=["1", "2"])
    session.add(ds)
    session.commit()    
```

Then we can run that test, echoing database queries, like this

```shell
# with pdm
pdm run test -k "weird_db_thing" --echo-queries -s
# with venv
python -m pytest -k "weird_db_thing --echo-queries -s
```

Where

- `-k` selects the test to run by matching against the test function name
- `--echo-queries` configures the database to echo the queries!
- `-s` prevents pytest from capturing stdout



