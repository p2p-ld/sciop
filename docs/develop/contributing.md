# Contributing

We welcome contributions of all kinds to Sciop including code 
contributions, typo fixes and documentation updates. This page outlines  
the development setups that will allow you to contribute.

<!-- is there a coc? what types of contributions are invited? -->

<div class="big-emphasis" markdown="1">

* The code is here: <https://codeberg.org/Safeguarding/sciop>
* The issues are here: <https://codeberg.org/Safeguarding/sciop/issues>
* The PRs are here: <https://codeberg.org/Safeguarding/sciop/pulls>

</div>

## Set up a Development Environment

### Fork the repository

If you plan to submit a pull request. Please follow the steps below:

- Fork the Sciop repository: https://codeberg.org/Safeguarding/sciop/fork
- Clone your forked repository so you can work locally
- Make a new branch in your fork for each pull request that you submit.

```shell
git clone https://codeberg.org/my-user-name/sciop
cd sciop
git switch -c new-branch
```

### Optional: Install Python

Most operating systems come with Python installed.
Sciop requires `python>=3.11`.
If you have an older version of Python, you'll need to install 3.11 or higher. 

In case you use an environment manager like conda, you may want to first check where your default Python lives:

```shell
which python
```

Then, check the default version of Python:

```shell
python --version
```

If you need a newer version of Python, use `pyenv` : https://github.com/pyenv/pyenv

See the [pyenv docs](https://github.com/pyenv/pyenv?tab=readme-ov-file#a-getting-pyenv) for platform-specific instructions, but generally:

- [Install pyenv](https://github.com/pyenv/pyenv?tab=readme-ov-file#a-getting-pyenv)

```shell
curl -fsSL https://pyenv.run | bash
```

- Add pyenv config to your favorite shell

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
- Install Python >= 3.11

```shell
# List python versions
pyenv install --list

# Install a specific version
pyenv install 3.13.1

# Activate that version globally
pyenv global 3.13.1
```

### Install `sciop`

sciop uses [`pdm`](https://pdm-project.org/en/latest/) for packaging and dependency management.
We recommend that you use PDM too; however, Sciop can be installed with pip as well (see below).

Instructions for installing Sciop using both tools are below. 

=== "Use PDM (preferred)"

    If you don't already have PDM installed, you can install it into your current working environment like this:

    ```shell
    python -m pip install pdm
    ```

    Once PDM is installed:

    * open your favorite shell 
    * cd into the `sciop` root directory,
    * use pdm to install all dependencies into a venv (by default in `./.venv`) using the command below

    ```shell
    pdm install --with dev
    ```

    The `--with dev` flag tells PDM to install both the project and all 
    project dependencies listed in the `pyproject.toml` file. PDM will also create environments setup in our pyproject.toml file that allow you to build documentation, run tests and build and run sciop locally. 

=== "Use pip"

    1. To setup your development environment using pip, first, make a virtual environment and activate it.

    ```shell
    python -m venv ./.venv
    ./.venv/bin/activate
    ```

    2. Install sciop in *editable* mode

    ```shell
    pip install -e .
    ```

## Running `sciop` in development mode

!!! note
    
    When using PDM, to run commands in the virtual environment, use `pdm run`.
    A collection of scripts has been created for sciop development,
    see all that are available with `pdm run --list` .

    Some of the `pdm` commands just wrap sciop cli commands,
    like `pdm run start` is just running `sciop start` within the pdm venv.
    For all other sciop cli commands, just prepend them with `pdm run`,
    so e.g. to run `sciop config copy` you would run `pdm run sciop config copy`.

    See the available sciop cli commands with `sciop --help` (or `pdm run sciop --help`).


Create a configuration from the defaults. 
This configuration controls how sciop runs, so for your development environment
default values should be filled in
like the host being `localhost` and the database being `db.dev.sqlite`.

```shell
sciop config copy
```

!!! tip

    See all available options and syntax in the full [config](../python/config.md) documentation

In the Sciop config, two fields are required and must be set for the application to run:

1. `SCIOP_ENV`: one of `dev`, `test` or `prod`. 
    * If you plan to make a Sciop instance publicly available, you must use `prod` mode.
    * If you plan to work locally, use `dev` mode,`test` mode is automatically used during tests.
    * IMPORTANT: Do not re-use the same database between a `dev`/`test` and `prod` instance, 
      e.g. if the `SCIOP_DB` location is explicitly set to something other than the defaults.

2. `SCIOP_SECRET_KEY`: must be a securely-generated random hex value.
  A key can be generated with `openssl rand -hex 32`,
  and a random key is generated for you by using `sciop config copy`

Once you have setup the required config, run a dev mode instance. 
This will create seed data and automatically reload the site when your code changes. Instructions for doing this using both PDM and pip are below:

=== "Use PDM (preferred)"

    ```shell
    pdm run start
    ```

=== "Use pip"

    ```shell
    sciop start
    ```

You can then login with the default root credentials:
(sciop will not allow you to run the prod instance with these)

* username: `root`
* password: `rootroot1234`

## Linting/Formatting

<!-- You could also use the ruff formater and remove black / keep it simpler?  -->

`sciop` uses `ruff` and `black` for linting and formatting.
Please run the code formatters before every commit. We will require them to be run before a Pull Request is merged.

=== "Use PDM (preferred)"

    The `pdm run format` command runs both Black and Ruff for you.

    ```bash
    pdm run format
    ❯ pdm run format
    All done! ✨ 🍰 ✨
    197 files left unchanged.
    warning: The following rules have been removed and ignoring them has no effect:
        - ANN101
        - ANN102

    All checks passed!
    ```

=== "Use pip"
    If you don't use PDM, you'll have to install and run each tool separately from your Python virtual environment.

    ```shell
    python -m black .
    python -m ruff check --fix
    ```

If you run `pdm run format` or `ruff check --fix`, it will  auto-fix most errors. The formatter will prompt you to fix 
any remaining errors that it can't fix.

## Testing

We use `pytest` for unit tests. All contributions should have 
unit tests that cover any added or changed functionality

To run the tests:

=== "Use PDM (preferred)"

    ```shell
    pdm run test
    ```
=== "Use pip"

    ```shell
    python -m pytest
    ```

### Writing Tests

Before you write tests, check out our existing tests to see how they are written. Also check out the `tests/fixtures` directory for utility fixtures to help you write tests with reusable parts.

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

```bash
alembic -c ./src/sciop/migrations/alembic.ini revision -m "{migration-slug}" --autogenerate
```

Where `{migration-slug}` is some description of the changes made in the migration.

The migration generator compares the current state of the ORM models to the current state of the database,
so the database must be equal to the state at the last migration. 

To get a clean database, before you generate the migration,
remove your development database and create a new one using alembic

```bash
alembic -c ./src/sciop/migrations/alembic.ini upgrade head
```

Then generate the migration with the command above.

Migrations can be tested with pytest



=== "Use PDM (preferred)"

    ```bash
    pdm run pytest tests/test_migrations.py
    ```

=== "Use pip"

    ```bash
    python -m pytest tests/test_migrations.py
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

You can use PDM to build and serve the docs locally for interactive development, like this:

```bash
pdm run docs
```

### Add a new docs page

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

Add this: 

```yaml
nav:
  - index.md
  - Intro:
    - intro/index.md
    - # ...
    - intro/new.md
```

### Move a page

If you need to move/rename a page, make a redirect from the old page.

For example to move `docs/intro/old.md` to `docs/intro/new.md`, add:

```yaml
plugins:
  - redirects:
      redirect_maps:
        "intro/old.md": "intro/new.md"
```

to the mkdocs.yml file.
