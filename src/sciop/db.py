import importlib.resources
from typing import Optional

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from sciop.config import config

engine = create_engine(str(config.sqlite_path))


def get_session():
    maker = sessionmaker(class_=Session, autocommit=False, autoflush=False, bind=engine)

    try:
        db = maker()
        yield db
    finally:
        db.close()


def create_tables():
    """
    Create tables and stamps with an alembic version

    Args:
        engine:
        config:

    References:
        - https://alembic.sqlalchemy.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch
    """

    SQLModel.metadata.create_all(engine)
    # check version here since creating the table is the same action as
    # ensuring our migration metadata is correct!
    ensure_alembic_version(engine)


def ensure_alembic_version(engine):
    """
    Make sure that our database is correctly stamped and migrations are applied.

    Raises:
        :class:`.exceptions.DBMigrationError` if migrations need to be applied!
    """
    # Handle database migrations and version stamping!
    alembic_config = get_alembic_config()

    command.ensure_version(alembic_config)
    version = alembic_version()

    # Check to see if we are up to date
    if version is None:
        # haven't been stamped yet, but we know we are
        # at the head since we just made the db.
        command.stamp(alembic_config, "head")
    else:
        try:
            command.check(alembic_config)
        except CommandError as e:
            # don't automatically migrate since it could be destructive
            raise RuntimeError("Database needs to be migrated! Run sciop migrate") from e


def get_alembic_config() -> AlembicConfig:
    return AlembicConfig(str(importlib.resources.files("sciop") / "migrations" / "alembic.ini"))


def alembic_version() -> Optional[str]:
    """
    for some godforsaken reason alembic's command for getting the
    db version ONLY PRINTS IT and does not return it.

    "fuck it we'll do it live"

    Args:
        engine (:class:`sqlalchemy.Engine`):

    Returns:
        str: Alembic version revision
        None: if there is no version yet!
    """
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
        version = result.fetchone()

    if version is not None:
        version = version[0]

    return version
