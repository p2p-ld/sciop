import importlib.resources
import random
from datetime import UTC, datetime
from pathlib import Path
from random import randint
from typing import TYPE_CHECKING, Generator, Optional

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine, func, select

from sciop.config import config

if TYPE_CHECKING:
    from faker import Faker

    from sciop.models import Account, Dataset, DatasetCreate, Upload

engine = create_engine(str(config.sqlite_path))
maker = sessionmaker(class_=Session, autocommit=False, autoflush=False, bind=engine)


def get_session() -> Generator[Session, None, None]:
    with maker() as session:
        yield session
    #     session = Session(engine)
    # try:
    #     yield session
    #     # db = maker()
    #     # yield db
    # finally:
    #     session.close()


def create_tables(engine: Engine = engine) -> None:
    """
    Create tables and stamps with an alembic version

    References:
        - https://alembic.sqlalchemy.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch
    """
    from sciop import models

    # FIXME: Super janky, do this in a __new__ or a decorator
    models.Dataset.register_events()
    models.Account.register_events()

    SQLModel.metadata.create_all(engine)
    # check version here since creating the table is the same action as
    # ensuring our migration metadata is correct!
    ensure_alembic_version()

    with maker() as session:
        models.Scope.ensure_enum_values(session=session)
        ensure_root(session=session)

    create_seed_data()


def ensure_alembic_version() -> None:
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


def create_seed_data() -> None:
    if config.env != "dev":
        return
    from faker import Faker

    from sciop import crud
    from sciop.models import AccountCreate, Dataset, DatasetCreate, Scope, Scopes

    fake = Faker()

    with maker() as session:
        admin = crud.get_account(username="admin", session=session)
        if not admin:
            admin = crud.create_account(
                account_create=AccountCreate(username="admin", password="adminadmin12"),
                session=session,
            )
        admin.scopes = [Scope.get_item(Scopes.admin.value, session)]
        session.add(admin)
        session.refresh(admin)

        uploader = crud.get_account(username="uploader", session=session)
        if not uploader:
            uploader = crud.create_account(
                account_create=AccountCreate(username="uploader", password="uploaderuploader12"),
                session=session,
            )
        uploader.scopes = [Scope.get_item(Scopes.upload.value, session)]
        session.add(uploader)
        session.refresh(uploader)

        unapproved_dataset = crud.get_dataset(dataset_slug="unapproved", session=session)
        if not unapproved_dataset:
            unapproved_dataset = crud.create_dataset(
                session=session,
                dataset_create=DatasetCreate(
                    slug="unapproved",
                    title="Unapproved Dataset",
                    publisher="An Agency",
                    homepage="https://example.com",
                    description="An unapproved dataset",
                    dataset_created_at=datetime.now(UTC),
                    dataset_updated_at=datetime.now(UTC),
                    priority="low",
                    source="web",
                    urls=["https://example.com/1", "https://example.com/2"],
                    tags=["unapproved", "test", "aaa", "bbb"],
                ),
            )
        unapproved_dataset.enabled = False
        session.add(unapproved_dataset)

        approved_dataset = crud.get_dataset(dataset_slug="approved", session=session)
        if not approved_dataset:
            approved_dataset = crud.create_dataset(
                session=session,
                dataset_create=DatasetCreate(
                    slug="approved",
                    title="Example Approved Dataset with Upload",
                    publisher="Another Agency",
                    homepage="https://example.com",
                    description="An unapproved dataset",
                    dataset_created_at=datetime.now(UTC),
                    dataset_updated_at=datetime.now(UTC),
                    priority="low",
                    source="web",
                    urls=["https://example.com/3", "https://example.com/4"],
                    tags=["approved", "test", "aaa", "bbb", "ccc"],
                ),
            )
        approved_dataset.enabled = True
        session.add(approved_dataset)
        session.commit()
        session.refresh(approved_dataset)

        approved_upload = crud.get_upload_from_short_hash(session=session, short_hash="abcdefgh")
        if not approved_upload:
            approved_upload = _generate_upload("abcdefgh", uploader, approved_dataset, session)
        approved_upload.enabled = True
        session.add(approved_upload)
        session.commit()

        unapproved_upload = crud.get_upload_from_short_hash(session=session, short_hash="unapprov")
        if not unapproved_upload:
            unapproved_upload = _generate_upload(
                "unapproved", uploader, unapproved_dataset, session
            )
        unapproved_upload.enabled = False
        session.add(unapproved_upload)
        session.commit()

        # generate a bunch of approved datasets to test pagination
        n_datasets = session.exec(select(func.count(Dataset.dataset_id))).one()
        if n_datasets < 500:
            for _ in range(500):
                generated_dataset = _generate_dataset(fake)
                dataset = crud.create_dataset(session=session, dataset_create=generated_dataset)
                dataset.dataset_created_at = datetime.now(UTC)
                dataset.dataset_updated_at = datetime.now(UTC)
                dataset.enabled = True
                session.add(dataset)
            session.commit()


def ensure_root(session: Session) -> Optional["Account"]:
    from sciop import crud
    from sciop.models import AccountCreate, Scope, Scopes

    root = crud.get_account(username=config.root_user, session=session)
    if not root:
        root = crud.create_account(
            account_create=AccountCreate(username=config.root_user, password=config.root_password),
            session=session,
        )
        scopes = [Scope.get_item(a_scope, session) for a_scope in Scopes.__members__.values()]
        root.scopes = scopes
        session.add(root)
        session.commit()
        session.refresh(root)

    config.root_password = None
    return root


def _generate_upload(
    name: str, uploader: "Account", dataset: "Dataset", session: Session
) -> "Upload":
    from torf import Torrent

    from sciop import crud
    from sciop.models import FileInTorrentCreate, TorrentFileCreate, UploadCreate

    torrent_file = config.torrent_dir / f"__{name}__"
    with open(torrent_file, "wb") as tfile:
        tfile.write(b"0" * 16384 * 4)

    file_size = torrent_file.stat().st_size

    torrent = Torrent(
        path=torrent_file,
        name=f"Example Torrent {name}",
        trackers=[["http://example.com/announce"]],
        comment="My comment",
        piece_size=16384,
    )
    torrent.generate()
    short_hash = name[0:8] if len(name) >= 8 else f"{name:x>8}"

    created_torrent = TorrentFileCreate(
        file_name=f"__{name}__.torrent",
        file_hash="abcdefghijklmnop",
        infohash="fiuwhgliauherliuh",
        short_hash=short_hash,
        total_size=16384 * 4,
        piece_size=16384,
        torrent_size=64,
        files=[FileInTorrentCreate(path=str(torrent_file.name), size=file_size)],
        trackers=["http://example.com/announce"],
    )
    created_torrent.filesystem_path.parent.mkdir(parents=True, exist_ok=True)
    torrent.write(created_torrent.filesystem_path, overwrite=True)
    created_torrent = crud.create_torrent(
        session=session, created_torrent=created_torrent, account=uploader
    )

    upload = UploadCreate(
        method="I downloaded it",
        description="Its all here bub",
        torrent_short_hash=short_hash,
    )

    created_upload = crud.create_upload(
        session=session, created_upload=upload, dataset=dataset, account=uploader
    )
    return created_upload


def _generate_dataset(fake: "Faker") -> "DatasetCreate":
    from faker import Faker

    from sciop.models import DatasetCreate, DatasetPartCreate, ExternalIdentifierCreate

    dataset_fake = Faker()

    title = fake.unique.bs()
    slug = title.lower().replace(" ", "-")

    parts = []
    base_path = Path(fake.unique.file_path(depth=2, extension=tuple()))

    for i in range(random.randint(1, 5)):
        part_slug = base_path / dataset_fake.unique.file_name(extension="")
        paths = [str(part_slug / dataset_fake.unique.file_name()) for i in range(5)]
        part = DatasetPartCreate(part_slug=str(part_slug), paths=paths)
        parts.append(part)

    return DatasetCreate(
        slug=slug,
        title=title,
        publisher=fake.company(),
        homepage=fake.url(),
        description=fake.text(1000),
        priority="low",
        source="web",
        urls=[fake.url() for _ in range(3)],
        tags=[f for f in [fake.word().lower() for _ in range(3)] if len(f) > 2],
        external_identifiers=[
            ExternalIdentifierCreate(
                type="doi",
                identifier=f"10.{randint(1000,9999)}/{fake.word().lower()}.{randint(10000,99999)}",
            )
        ],
        parts=parts,
    )
