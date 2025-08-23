from typing import Callable

import pytest
from _pytest.monkeypatch import MonkeyPatch
from alembic.config import Config as AlembicConfig
from sqlalchemy import Connection, Engine, Transaction, create_engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel
from sqlmodel.pool import StaticPool


def _engine(request: pytest.FixtureRequest) -> Engine:
    if request.config.getoption("--file-db"):
        from sciop.config import get_config

        engine_kwargs = {
            "pool_size": get_config().db.pool_size,
            "max_overflow": get_config().db.overflow_size,
        }
        if request.config.getoption("--echo-queries"):
            engine_kwargs["echo"] = True

        assert (
            str(get_config().paths.sqlite) == "db.test.sqlite"
        ), "Must use db.test.sqlite for file dbs in testing"
        engine = create_engine(str(get_config().paths.sqlite), **engine_kwargs)
    else:
        engine = _in_memory_engine(request)
    return engine


@pytest.fixture()
def engine(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Engine:
    from sciop import db

    engine = _engine(request)
    monkeypatch.setattr(db, "_engine", engine)
    monkeypatch.setattr(db, "_make_engine", lambda: _engine(request))
    yield engine
    engine.dispose(close=True)


@pytest.fixture(scope="module")
def engine_module(request: pytest.FixtureRequest, monkeypatch_module: pytest.MonkeyPatch) -> Engine:
    from sciop import db

    engine = _engine(request)
    monkeypatch_module.setattr(db, "_engine", engine)
    monkeypatch_module.setattr(db, "_make_engine", lambda: _engine(request))
    yield engine
    engine.dispose(close=True)


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
) -> tuple[Session, list[tuple[Transaction, Connection]]]:
    from sciop import db
    from sciop.api import deps
    from sciop.app import app
    from sciop.models.mixins import EditableMixin

    transactions = []

    if request.config.getoption("--file-db"):
        session, connection, trans = _file_session(engine)
        transactions.append((trans, connection))

        def get_session_override() -> Session:
            nonlocal transactions
            session, connection, trans = _file_session(engine)
            # don't rollback here, or we'll rollback in the middle of the test.
            # rollback at the end
            transactions.append((trans, connection))
            session = EditableMixin.editable_session(session)
            yield session

    else:
        maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
        session = Session(engine, autoflush=False, autocommit=False)

        def get_session_override() -> Session:
            nonlocal maker
            with maker() as session:
                session = EditableMixin.editable_session(session)
                yield session
                session.close()

    monkeypatch.setattr(db, "get_session", get_session_override)
    monkeypatch.setattr(deps, "get_session", get_session_override)

    app.dependency_overrides[deps.raw_session] = get_session_override

    session = EditableMixin.editable_session(session)
    return session, transactions


def _session_end(
    session: Session,
    request: pytest.FixtureRequest,
    transactions: list[tuple[Transaction, Connection]] | None,
) -> None:

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


def _file_session(engine: Engine) -> tuple[Session, Connection, Transaction]:
    from sciop.db import get_maker

    maker = get_maker(engine)
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
