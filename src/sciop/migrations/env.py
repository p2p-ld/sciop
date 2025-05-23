from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from sciop.config import get_config
from sciop.models import SQLModel  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
url = config.get_main_option("sqlalchemy.url")
if url is None:
    # don't override if it's already been given to use explicitly
    config.set_main_option("sqlalchemy.url", get_config().paths.sqlite)


# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

target_metadata = SQLModel.metadata

IGNORE_NAMES = (
    "__search",
    "apscheduler",
)
"""partial names, if any table contains these substrings, ignore for migrations"""


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def include_name(name, type_, parent_names):
    if type_ == "table":
        return not any(substr in name for substr in IGNORE_NAMES)
    else:
        return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        dialect_name="sqlite",
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_schemas=True,
        include_name=include_name,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = context.config.attributes.get("connection", None)

    if connectable is None:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            dialect_name="sqlite",
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=True,
            include_name=include_name,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
