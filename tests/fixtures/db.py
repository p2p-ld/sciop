from typing import Callable

import pytest
from _pytest.monkeypatch import MonkeyPatch
from alembic.config import Config as AlembicConfig
from sqlalchemy import Connection, Engine, Transaction, create_engine
from sqlalchemy.exc import ProgrammingError
from sqlmodel import Session, SQLModel
from sqlmodel.pool import StaticPool


def _engine(request: pytest.FixtureRequest) -> Engine:
    if request.config.getoption("--file-db"):
        from sciop.db import engine
    else:
        engine = _in_memory_engine(request)
    return engine


@pytest.fixture()
def engine(request: pytest.FixtureRequest) -> Engine:
    return _engine(request)


@pytest.fixture(scope="module")
def engine_module(request: pytest.FixtureRequest) -> Engine:
    return _engine(request)


@pytest.fixture
def session(monkeypatch: MonkeyPatch, request: pytest.FixtureRequest, engine: Engine) -> Session:
    session, transactions = _session_start(monkeypatch, request, engine)
    yield session
    _session_end(session, request, transactions)


@pytest.fixture(scope="module")
def session_module(
    monkeypatch_module: MonkeyPatch, request: pytest.FixtureRequest, engine_module: Engine
) -> Session:
    monkeypatch = monkeypatch_module
    engine = engine_module
    session, transactions = _session_start(monkeypatch, request, engine)
    yield session
    _session_end(session, request, transactions)


def _session_start(
    monkeypatch: MonkeyPatch, request: pytest.FixtureRequest, engine: Engine
) -> tuple[Session, list[Transaction]]:
    from sciop import db, scheduler
    from sciop.api import deps
    from sciop.app import app
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
        session = Session(engine, autoflush=False, autocommit=False)

        def get_engine_override() -> Engine:
            nonlocal engine
            return engine

        def get_session_override() -> Session:
            session = Session(engine, autoflush=False, autocommit=False)
            session = EditableMixin.editable_session(session)
            yield session

        monkeypatch.setattr(scheduler, "get_engine", get_engine_override)
        monkeypatch.setattr(db, "get_engine", get_engine_override)

    monkeypatch.setattr(db, "get_session", get_session_override)
    monkeypatch.setattr(deps, "get_session", get_session_override)

    app.dependency_overrides[deps.raw_session] = get_session_override

    session = EditableMixin.editable_session(session)
    return session, transactions


def _session_end(
    session: Session, request: pytest.FixtureRequest, transactions: list[Transaction] | None
) -> Session:
    yield session

    try:
        session.close()
    except ProgrammingError as e:
        if "closed database" not in str(e):
            # fine, from tearing down server in selenium tests
            raise e

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
    create_tables(engine, check_migrations=False, check_existing=False)

    return engine


def _file_session() -> tuple[Session, Connection, Transaction]:
    from sciop.db import engine, maker

    connection = engine.connect()

    # begin a non-ORM transaction
    trans = connection.begin()
    session = maker(bind=connection)

    return session, connection, trans


@pytest.fixture
def recreate_models(engine: Engine) -> Callable[[], "Engine"]:
    """Callable fixture to recreate models after any inline definitions of tables"""

    def _recreate_models() -> "Engine":
        SQLModel.metadata.create_all(engine)
        return engine

    return _recreate_models


@pytest.fixture
def alembic_config() -> AlembicConfig:
    from sciop.db import get_alembic_config

    return get_alembic_config()
