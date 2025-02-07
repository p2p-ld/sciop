import importlib.resources
from typing import TYPE_CHECKING, Generator, Optional

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.util.exc import CommandError
from sqlalchemy import text, select, func
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from sciop.config import config

if TYPE_CHECKING:
    from sciop.models import Account, Dataset, DatasetInstance
    from faker import Faker

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
    from sciop.models import AccountCreate, DatasetCreate, Scope, Scopes, Dataset
    from faker import Faker
    fake = Faker()

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

        uploader = crud.get_account(username="uploader", session=session)
        if not uploader:
            uploader = crud.create_account(
                account_create=AccountCreate(username="uploader", password="uploaderuploader"),
                session=session
            )
        uploader.scopes = [Scope(name=Scopes.upload)]
        session.add(uploader)
        session.refresh(uploader)

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

        approved_dataset = crud.get_dataset(dataset_slug="approved", session=session)
        if not approved_dataset:
            approved_dataset = crud.create_dataset(
                session=session,
                dataset_create=DatasetCreate(
                    slug="approved",
                    title="Example Approved Dataset with Upload",
                    agency="Another Agency",
                    homepage="example.com",
                    description="An unapproved dataset",
                    priority="low",
                    source="web",
                    urls=["example.com/3", "example.com/4"],
                    tags=["approved", "test", "aaa", "bbb", "ccc"],
                ),
            )
        approved_dataset.enabled = True
        session.add(approved_dataset)
        session.commit()
        session.refresh(approved_dataset)

        approved_upload = crud.get_instance_from_short_hash(session=session, short_hash="abcdefgh")
        if not approved_upload:
            approved_upload = _generate_instance(uploader, approved_dataset, session)
        approved_upload.enabled = True
        session.add(approved_upload)
        session.commit()

        # generate a bunch of approved datasets to test pagination
        n_datasets = session.query(Dataset).count()
        if n_datasets < 500:
            for _ in range(500):
                generated_dataset = _generate_dataset(fake)
                session.add(generated_dataset)
            session.commit()



def _generate_instance(uploader: "Account", dataset: "Dataset", session: Session) -> "DatasetInstance":
    from torf import Torrent

    from sciop import crud
    from sciop.models import DatasetInstanceCreate, FileInTorrentCreate, TorrentFileCreate

    torrent_path = config.torrent_dir / "__example__.torrent"
    torrent_file = config.torrent_dir / "__example__"
    with open(torrent_file, 'wb') as tfile:
        tfile.write(b'0' * 16384 * 4)

    torrent = Torrent(
        path=torrent_file,
        name="Example Torrent",
        trackers=[["http://example.com/announce"]],
        comment="My comment",
        piece_size=16384,
    )
    torrent.generate()
    created_torrent = TorrentFileCreate(
        file_name="__example__.torrent",
        hash="abcdefghijklmnop",
        short_hash="abcdefgh",
        total_size=16384 * 4,
        piece_size=16384,
        torrent_size=64,
        files=[FileInTorrentCreate(path=str(torrent_file), size=2048)],
        trackers=["http://example.com/announce"]
    )
    created_torrent.filesystem_path.parent.mkdir(parents=True, exist_ok=True)
    torrent.write(created_torrent.filesystem_path, overwrite=True)
    created_torrent = crud.create_torrent(session=session, created_torrent=created_torrent, account=uploader)

    instance = DatasetInstanceCreate(
        method="I downloaded it",
        description="Its all here bub",
        torrent_short_hash="abcdefgh",
    )

    created_instance = crud.create_instance(
        session=session, created_instance=instance, dataset=dataset, account=uploader
    )
    return created_instance

def _generate_dataset(fake: "Faker") -> "Dataset":
    from sciop.models import Dataset, DatasetURL, DatasetTag
    title = fake.unique.bs()
    slug = title.lower().replace(" ", "-")

    return Dataset(
        slug=slug,
        title=title,
        agency=fake.company(),
        homepage=fake.url(),
        description=fake.text(1000),
        priority="low",
        source="web",
        urls=[DatasetURL(url=fake.url()) for _ in range(3)],
        tags=[DatasetTag(tag=fake.word().lower()) for _ in range(3)],
        enabled=True
    )