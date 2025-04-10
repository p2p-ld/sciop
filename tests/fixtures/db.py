from typing import Callable

import pytest
from _pytest.monkeypatch import MonkeyPatch
from alembic.config import Config as AlembicConfig
from sqlalchemy import Connection, Engine, Transaction, create_engine
from sqlmodel import Session, SQLModel
from sqlmodel.pool import StaticPool

# @pytest.fixture(scope="session", autouse=True)
# def create_tables(monkeypatch_session: "MonkeyPatch", monkeypatch_config: None) -> None:
#     from sciop.config import config
#     from sciop.db import create_tables
#
#     engine = create_engine(str(config.sqlite_path))
#     create_tables(engine, check_migrations=False)


@pytest.fixture()
def engine(request: pytest.FixtureRequest) -> Engine:
    if request.config.getoption("--file-db"):
        engine, connection, trans = _file_session()
    else:
        engine, connection, trans = _in_memory_engine(request)


@pytest.fixture
def session(monkeypatch: MonkeyPatch, request: pytest.FixtureRequest) -> Session:
    from sciop import db, scheduler
    from sciop.api import deps
    from sciop.app import app
    from sciop.frontend import templates
    from sciop.models.mixins import EditableMixin

    transactions = []

    if request.config.getoption("--file-db"):
        session, connection, trans = _file_session()
        transactions.append((trans, connection))

        def get_session_override() -> Session:
            nonlocal transactions
            session, connection, trans = _file_session()
            # don't rollback here, or we'll rollback in the middle of the test.
            # rollback at the end
            transactions.append((trans, connection))
            session = EditableMixin.editable_session(session)
            yield session

    else:
        engine = _in_memory_engine(request)
        session = Session(engine)

        def get_engine_override() -> Engine:
            nonlocal engine
            return engine

        def get_session_override() -> Session:
            session = Session(engine)
            session = EditableMixin.editable_session(session)
            yield session

        monkeypatch.setattr(scheduler, "get_engine", get_engine_override)
        monkeypatch.setattr(db, "get_engine", get_engine_override)

    monkeypatch.setattr(db, "get_session", get_session_override)
    monkeypatch.setattr(templates, "get_session", get_session_override)
    monkeypatch.setattr(deps, "get_session", get_session_override)

    app.dependency_overrides[deps.raw_session] = get_session_override

    session = EditableMixin.editable_session(session)
    yield session

    # try:
    session.close()
    # except ProgrammingError as e:
    #     if "closed database" not in str(e):
    #         # fine, from tearing down server in selenium tests
    #         raise e

    if request.config.getoption("--file-db"):
        for trans, connection in transactions:
            if request.config.getoption("--persist-db"):
                trans.commit()
            else:
                trans.rollback()  # roll back to the SAVEPOINT
            connection.close()


def _in_memory_engine(request: pytest.FixtureRequest) -> Engine:
    from sciop.db import create_tables

    engine_kwargs = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
    if request.config.getoption("--echo-queries"):
        engine_kwargs["echo"] = True

    engine = create_engine("sqlite://", **engine_kwargs)
    create_tables(engine, check_migrations=False)

    return engine


def _file_session() -> tuple[Session, Connection, Transaction]:
    from sciop.db import engine, maker

    connection = engine.connect()

    # begin a non-ORM transaction
    trans = connection.begin()
    session = maker(bind=connection)

    return session, connection, trans


@pytest.fixture
def recreate_models() -> Callable[[], "Engine"]:
    """Callable fixture to recreate models after any inline definitions of tables"""

    def _recreate_models() -> "Engine":
        from sciop.db import get_engine

        engine = get_engine()
        SQLModel.metadata.create_all(engine)
        return engine

    return _recreate_models


@pytest.fixture
def alembic_config() -> AlembicConfig:
    from sciop.db import get_alembic_config

    return get_alembic_config()
