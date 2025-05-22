# Contributing

<div class="big-emphasis" markdown="1">

* The code is here: <https://codeberg.org/Safeguarding/sciop>
* The issues are here: <https://codeberg.org/Safeguarding/sciop/issues>
* The PRs are here: <https://codeberg.org/Safeguarding/sciop/pulls>

</div>

## Setting up a Development Environment

### Fork the repository

- Fork the repository: https://codeberg.org/Safeguarding/sciop/fork
- Clone your forked repository
- Make a new branch to work on

```shell
git clone https://codeberg.org/my-user-name/sciop
cd sciop
git switch -c new-branch
```

### Optional: Install Python

Most operating systems come with Python installed,
however Sciop requires `python>=3.11`.
If you have an older version, you'll need to install an updated version of python.

Check your version of python

```shell
python --version
```

If you need a newer version of python, use `pyenv` : https://github.com/pyenv/pyenv

See the docs for platform-specific instructions, but generally...

- Install pyenv

```shell
curl -fsSL https://pyenv.run | bash
```

- Add pyenv config to shell

<details>
<summary>Expand/collapse Bash instructions</summary>

```shell
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc

echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.profile
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.profile
echo 'eval "$(pyenv init - bash)"' >> ~/.profile

echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bash_profile
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bash_profile
echo 'eval "$(pyenv init - bash)"' >> ~/.bash_profile
```

</details>

<details>
<summary>Expand/collapse zshj instructions</summary>

```shell
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init - zsh)"' >> ~/.zshrc
```

</details>

- Restart your shell
- Install python

```shell
# list python versions
pyenv install --list

# install a specific version
pyenv install 3.13.1

# activate that version globally
pyenv global 3.13.1
```

### Install `sciop`

#### With `pdm`

sciop uses [`pdm`](https://pdm-project.org/en/latest/) for packaging and dependency management,
we recommend you use it too, it's a wonderful tool, but sciop can be installed with pip as well (see below)

If you don't already have pip you can install it (globally) like

```shell
python -m pip install pdm
```

and then from the `sciop` root directory,
use pdm to install all dependencies into a venv (by default in `./.venv`)

```shell
pdm install --with dev
```

#### With `pip`

Make a virtual environment and activate it

```shell
python -m venv ./.venv
./.venv/bin/activate
```

Install sciop using an *editable install*

```shell
pip install -e .
```

## Running `sciop` in dev mode

!!! note
    
    For `sciop` cli commands that don't have a pdm alias when using pdm,
    just prepend `pdm run` like `pdm run sciop start` 


Create a configuration:

```shell
sciop config copy
```

!!! tip

    See all available options and syntax in the full [config](../python/config.md) documentation

Two fields *must* be set:

- `SCIOP_ENV`: one of `dev`, `test` or `prod`. 
  One should *only* make a sciop instance publicly available in `prod` mode.
  `dev` mode is for local development purposes, as is `test`.
  You must ensure that you do not re-use the same db between a `dev`/`test` and `prod`
  instance, e.g. if the `SCIOP_DB` location is explicitly set to something other than the defaults.
- `SCIOP_SECRET_KEY`: must be a securely-generated random hex value.
  A key can be generated with `openssl rand -hex 32`.

Then run the dev mode instance - 
this will create seed data and automatically reload the site when your code changes

**with `pdm`**

```shell
pdm run start
```

**with `pip`**

```shell
sciop start
```

You can then login with the default root credentials:
(sciop will not allow you to run the prod instance with these)

* username: `root`
* password: `rootroot1234`

## Linting/Formatting

`sciop` uses `ruff` and `black` for linting and formatting.

```shell
pdm run format
# or
black .
ruff check --fix
```

This should typically be run before every commit, but must be done before a PR is merged.
The `ruff check --fix` call should auto-fix most errors and prompt you to fix the remaining errors.

## Testing

We use `pytest` for unit tests, 
and all contributions should have unit tests that cover any added or changed functionality

To run the tests:

```angular2html
pdm run test
# or
python -m pytest
```

### Writing Tests

Look for existing tests to see how tests are commonly written,
and see the `tests/fixtures` directory for utility fixtures to help you write tests.

!!! danger "Always use the db fixtures!"

    Do not use the in-package `db.get_session`, `db.get_engine` database accessors in tests! 
    Always use the `session` and `engine` fixtures 
    (or their module-scoped `session_module`/`engine_module` siblings)
    to ensure that tests do not modify the development databases.
    The test setup tries to protect you from this, but it can't protect against everything!

    We also *do not* recommend running the tests from the directory where you have 
    a production instance of sciop running to avoid accidentally modifying your production database!

Some common fixtures you may need to use are...

**Fabricators**

To create dummy versions of common objects.
The database is rolled back between every test, so data also needs to be created in every test.

Fabricators, like all fixtures, are used by adding them to the test function signature.
Fabricators then take any kwargs passed to them and use those to overwrite the default values

```python
def test_fabricators(dataset, upload, account):
    acc = account(username='smileyjim', scopes=["root", "admin"])
    ds = dataset(slug="cool-data", account=acc)
    # ...
```

**TestClient**

For tests that require the API, you can get a test client that behaves similarly to `requests`
with the `client` fixture:

```python
def test_api_request(client):
    get_result = client.get("/datasets/cool-data")
    post_result = client.post(f"{config.api_prefix}/datasets/", json={...})

```

**Playwright Tests**

For tests that not only require the client, but need to simulate a full browser session,
use the `page` fixture (or `page_as_admin`, `page_as_user` for a pre-logged in session):

```python
@pytest.mark.playwright
@pytest.mark.asyncio(loop_scope="session")
async def test_playwright_thing(page):
    await page.goto("http://127.0.0.1:8080/datasets/")
```

Mark all playwright tests with `pytest.mark.playwright` as above.

Playwright tests must be async and must set their loop scope to session in order to work.

Note that *most tests do not require playwright,* 
and playwright tests are comparatively expensive and should be used sparingly.
Playwright tests are mostly useful when one needs to specifically test ux or accessibility behavior
that can't be tested using the static HTML returned by the `TestClient`

While working with playwright tests, you can invoke pytest with the `--headed` flag to show the browser.

Playwright has a code generation mode that is useful to get the general shape of a test,
though you should always ensure that the generated code reflects exactly what you had intended to test.

To invoke it, do whatever setup you need to do for the test, and then await `page.pause()`
(after invoking pytest with `--headed`)

```python
@pytest.mark.playwright
@pytest.mark.asyncio(loop_scope="session")
async def test_playwright_thing(page):
    # use fixture functions to make datasets, whatever...
    await page.goto("http://127.0.0.1:8080/datasets/")
    await page.pause()
```

The browser window should appear along with a second "playwright inspector" window.
Click "record" in the playwright inspector. 
After you make one action, you should be able to chang ethe "target" to "Library async"
(at the time of writing, there is a mode for *synchronous* pytest output,
but not async.)

Generate the code, and then copy it into the body of your test! 
You'll likely need to swap out some of the values and use `expect` statements,
but the code generator can handle some of the boilerplate.

## DB Migrations


Any changes to the database must have corresponding migrations.

Migrations can be [autogenerated with alembic](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)

```
alembic -c ./src/sciop/migrations/alembic.ini revision -m "{migration-slug}" --autogenerate
```

Where `{migration-slug}` is some description of the changes made in the migration.

The migration generator compares the current state of the ORM models to the current state of the database,
so the database must be equal to the state at the last migration. 

To get a clean database, before you generate the migration,
remove your development database and create a new one using alembic

```
alembic -c ./src/sciop/migrations/alembic.ini upgrade head
```

Then generate the migration with the command above.

Migrations can be tested with pytest

```
python -m pytest tests/test_migrations.py
# or
pdm run pytest tests/test_migrations.py
```

To test trickier migrations, you might want to create a version of the db in the previous state
to compare what happens after the migration.

```shell
rm db.dev.sqlite
git switch main
pdm run start

# wait for startup... then quit

git switch {feature-branch}
pdm run migrate
```

## Writing Docs

The docs are written with [mkdocs](https://www.mkdocs.org/) and 
[mkdocs-material](https://squidfunk.github.io/mkdocs-material/).

### Adding a new page

To add a new page, create a new `.md` file in the relevant folder and add it to the 
`nav` section in the `mkdocs.yml` configuration.
Rather than setting the title in the `nav` section, 
set the title in the markdown document.

If the section has an index page, make sure to also add your new page to the index.

e.g. for my new page:

`docs/intro/new.md`
```markdown
# My New Page

Hello this is a new page
```

Add this 

```yaml
nav:
  - index.md
  - Intro:
    - intro/index.md
    - # ...
    - intro/new.md
```


### Moving a page

If you need to move/rename a page, make a redirect from the old page.

So e.g. if i am moving `docs/intro/old.md` to `docs/intro/new.md`, add

```yaml
plugins:
  - redirects:
      redirect_maps:
        "intro/old.md": "intro/new.md"
```






