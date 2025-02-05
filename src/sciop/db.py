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
maker = sessionmaker(class_=Session, autocommit=False, autoflush=False, bind=engine)


def get_session() -> Session:
    with maker() as session:
        yield session
    #     session = Session(engine)
    # try:
    #     yield session
    #     # db = maker()
    #     # yield db
    # finally:
    #     session.close()


def create_tables():
    """
    Create tables and stamps with an alembic version

    Args:
        engine:
        config:

    References:
        - https://alembic.sqlalchemy.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch
    """
    from sciop import models
    models.Dataset.register_events()

    SQLModel.metadata.create_all(engine)
    # check version here since creating the table is the same action as
    # ensuring our migration metadata is correct!
    ensure_alembic_version(engine)
    create_seed_data(engine)


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


def create_seed_data(engine):
    if config.env not in ("dev", "test"):
        return
    from sciop import crud
    from sciop.models import AccountCreate, DatasetCreate, Scope, Scopes

    with maker() as session:
        # session = get_session()
        admin = crud.get_account(username="admin", session=session)
        if not admin:
            admin = crud.create_account(
                account_create=AccountCreate(username="admin", password="adminadmin"),
                session=session,
            )

        scopes = [Scope(name=a_scope) for a_scope in Scopes.__members__.values()]
        admin.scopes = scopes
        session.add(admin)
        session.commit()
        session.refresh(admin)

        unapproved_dataset = crud.get_dataset(dataset_slug="unapproved", session=session)
        if not unapproved_dataset:
            unapproved_dataset = crud.create_dataset(
                session=session,
                dataset_create=DatasetCreate(
                    slug="unapproved",
                    title="Unapproved Dataset",
                    agency="An Agency",
                    homepage="example.com",
                    description="An unapproved dataset",
                    priority="low",
                    source="web",
                    urls=["example.com/1", "example.com/2"],
                    tags=["unapproved", "test", "aaa", "bbb"],
                ),
            )
        unapproved_dataset.enabled = False
        session.add(unapproved_dataset)
        session.commit()
        session.refresh(unapproved_dataset)
