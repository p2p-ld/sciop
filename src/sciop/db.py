import importlib.resources
import random
from typing import TYPE_CHECKING, Generator, Optional

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.engine.base import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine, func, select

from sciop.config import get_config

if TYPE_CHECKING:

    from sciop.models import Account

_engine: Engine | None = None
_maker: sessionmaker | None = None


def get_session() -> Generator[Session, None, None]:
    from sciop.models.mixins import EditableMixin

    maker = get_maker()

    with maker() as session:
        session = EditableMixin.editable_session(session)
        yield session


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            str(get_config().paths.sqlite),
            echo=get_config().db.echo,
            pool_size=get_config().db.pool_size,
            max_overflow=get_config().db.overflow_size,
        )
    return _engine


def get_maker(engine: Engine | None = None) -> sessionmaker:
    global _maker
    if _maker is None:
        if engine is None:
            engine = get_engine()
        _maker = sessionmaker(class_=Session, autocommit=False, autoflush=False, bind=engine)
    return _maker


def create_tables(
    engine: Engine | None = None, check_migrations: bool = True, check_existing: bool = True
) -> None:
    """
    Create tables and stamps with an alembic version

    References:
        - https://alembic.sqlalchemy.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch
    """
    if engine is None:
        engine = get_engine()

    from sciop import models

    # FIXME: Super janky, do this in a __new__ or a decorator
    models.Dataset.register_events()
    models.Account.register_events()
    models.Upload.register_events()

    SQLModel.metadata.create_all(engine, checkfirst=check_existing)
    if check_migrations and get_config().env != "test":
        # check version here since creating the table is the same action as
        # ensuring our migration metadata is correct!
        ensure_alembic_version(engine)

    with Session(engine) as session:
        models.Scope.ensure_enum_values(session=session)
        if get_config().env != "test":
            ensure_root(session=session)

    create_seed_data()


def ensure_alembic_version(engine: Engine) -> None:
    """
    Make sure that our database is correctly stamped and migrations are applied.

    Raises:
        :class:`.exceptions.DBMigrationError` if migrations need to be applied!
    """
    # Handle database migrations and version stamping!
    alembic_config = get_alembic_config()

    command.ensure_version(alembic_config)
    version = alembic_version(engine)

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
            raise RuntimeError(f"Database needs to be migrated! Run `pdm run migrate`\n{e}") from e


def get_alembic_config() -> AlembicConfig:
    return AlembicConfig(str(importlib.resources.files("sciop") / "migrations" / "alembic.ini"))


def alembic_version(engine: Engine) -> Optional[str]:
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
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version_num FROM alembic_version"))
            version = result.fetchone()

        if version is not None:
            version = version[0]

        return version
    except OperationalError as e:
        if "no such table" in str(e):
            return None
        else:
            raise e


def create_seed_data(n: int = 100) -> None:
    if get_config().env != "dev":
        return

    from faker import Faker
    from tqdm import trange

    from sciop import crud
    from sciop.logging import init_logger
    from sciop.models import Dataset
    from sciop.testing.fabricators import Fabricator

    fake = Faker()
    maker = get_maker()

    with maker() as session:
        fab = Fabricator(session)
        accts = [
            {
                "username": "admin",
                "password": "adminadmin12",
                "scopes": ["admin"],
            },
            {
                "username": "uploader",
                "password": "uploaderuploader12",
                "scopes": ["upload"],
            },
            {"username": "rando", "password": "randorando123"},
        ]
        dsets = [
            {"slug": "unapproved", "title": "Unapproved Dataset", "is_approved": False},
            {
                "slug": "approved",
                "title": "Example Approved Dataset with Upload",
                "is_approved": True,
            },
            {
                "slug": "removed",
                "title": "Example removed Dataset with Upload",
                "is_approved": True,
                "is_removed": True,
            },
            {
                "slug": "averylongnamewithnobreakpoints" * 3,
                "title": "averylongnamewithnobreakpoints" * 3,
                "is_approved": True,
            },
            {
                "slug": "dataset-with-webseeds",
                "title": "the uploads in here have webseeds",
                "is_approved": True,
            },
        ]
        uls = [
            {"name": "abcdefgh", "dataset": "approved", "is_approved": True},
            {"name": "unapproved", "dataset": "unapproved", "is_approved": False},
            {"name": "removed1", "dataset": "approved", "is_approved": True, "is_removed": True},
            {
                "name": "averylongnamewithnobreakpoints" * 3,
                "dataset": "averylongnamewithnobreakpoints" * 3,
                "is_approved": True,
            },
            {
                "name": "webseed torrent",
                "dataset": "dataset-with-webseeds",
                "is_approved": True,
                "torrent_kwargs": {
                    "url_list": [
                        "https://example.com/data",
                        "https://other.example.com/parent/data",
                    ]
                },
                "torrentfile_kwargs": {
                    "webseeds": [
                        "https://example.com/data",
                        "https://other.example.com/parent/data",
                    ]
                },
            },
        ]

        accounts = {}
        datasets = {}
        uploads = {}

        # if we've already generated the seed data, return
        n_datasets = session.exec(select(func.count(Dataset.dataset_id))).one()
        if n_datasets > n:
            return

        logger = init_logger("db.seed_data")
        logger.info("Creating seed data")

        for acct in accts:
            account = crud.get_account(username=acct["username"], session=session)
            accounts[acct["username"]] = account if account else fab.account(**acct)

        for dset in dsets:
            ds = crud.get_dataset(dataset_slug=dset["slug"], session=session)
            datasets[dset["slug"]] = ds if ds else fab.dataset(**dset)

        for ul in uls:
            ul["dataset"] = datasets[ul["dataset"]]
            ul["account"] = accounts["uploader"]
            upload = crud.get_upload_from_infohash(session=session, infohash=ul["name"][:8])
            uploads[ul["name"]] = upload if upload else fab.random_upload(**ul)

        # generate a bunch of approved datasets to test pagination
        for _ in trange(n):
            dataset = fab.random_dataset(fake=fake, account=accounts["rando"], commit=False)
            dataset.uploads = [
                fab.random_upload(
                    name=fake.word(),
                    account=accounts["uploader"],
                    dataset=dataset,
                    commit=False,
                )
                for _ in range(random.randint(1, 3))
            ]
            session.add(dataset)
        session.commit()

        logger.info("Seed data created")


def ensure_root(session: Session) -> Optional["Account"]:
    from sciop import crud
    from sciop.models import AccountCreate, Scope
    from sciop.types import Scopes

    cfg = get_config()
    if not (cfg.root_user and cfg.root_password):
        return

    root = crud.get_account(username=cfg.root_user, session=session)
    if not root:
        root = crud.create_account(
            account_create=AccountCreate(
                username=get_config().root_user, password=get_config().root_password
            ),
            session=session,
        )
        scopes = [Scope.get_item(a_scope, session) for a_scope in Scopes.__members__.values()]
        root.scopes = scopes
        session.add(root)
        session.commit()
        session.refresh(root)

    cfg.root_password = None
    return root
