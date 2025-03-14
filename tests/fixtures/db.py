from typing import Callable

import pytest
from _pytest.monkeypatch import MonkeyPatch
from alembic.config import Config as AlembicConfig
from sqlalchemy import Connection, Engine, Transaction, create_engine
from sqlalchemy.exc import ProgrammingError
from sqlmodel import Session, SQLModel
from sqlmodel.pool import StaticPool


@pytest.fixture(scope="session", autouse=True)
def create_tables(monkeypatch_session: "MonkeyPatch", monkeypatch_config: None) -> None:
    from sciop.config import config
    from sciop.db import create_tables

    engine = create_engine(str(config.sqlite_path))
    create_tables(engine, check_migrations=False)


@pytest.fixture
def session(monkeypatch: MonkeyPatch, request: pytest.FixtureRequest) -> Session:
    from sciop import db, scheduler
    from sciop.api import deps
    from sciop.app import app
    from sciop.db import get_session
    from sciop.frontend import templates
    from sciop.models.mixins import EditableMixin

    if request.config.getoption("--file-db"):
        engine, session, connection, trans = _file_session()
    else:
        engine, session, connection, trans = _in_memory_session()

    def get_session_override() -> Session:
        yield session

    def get_engine_override() -> Engine:
        return engine

    monkeypatch.setattr(db, "get_session", get_session_override)
    monkeypatch.setattr(templates, "get_session", get_session_override)
    monkeypatch.setattr(deps, "get_session", get_session_override)
    monkeypatch.setattr(db, "get_engine", get_engine_override)
    monkeypatch.setattr(scheduler, "get_engine", get_engine_override)

    app.dependency_overrides[get_session] = get_session_override

    yield session

    try:
        session.close()
    except ProgrammingError as e:
        if "closed database" not in str(e):
            # fine, from tearing down server in selenium tests
            raise e

    if request.config.getoption("--file-db"):
        if request.config.getoption("--persist-db"):
            trans.commit()
        else:
            trans.rollback()  # roll back to the SAVEPOINT
        connection.close()


def _in_memory_session() -> tuple[Engine, Session, None, None]:
    from sciop.db import create_tables
    from sciop.models.mixins import EditableMixin

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    create_tables(engine, check_migrations=False)
    session = Session(engine)
    session = EditableMixin.editable_session(session)
    return engine, session, None, None


def _file_session() -> tuple[Engine, Session, Connection, Transaction]:
    from sciop.db import engine, maker
    from sciop.models.mixins import EditableMixin

    connection = engine.connect()

    # begin a non-ORM transaction
    trans = connection.begin()
    session = maker(bind=connection)
    session = EditableMixin.editable_session(session)
    return engine, session, connection, trans


@pytest.fixture
def recreate_models() -> Callable[[], "Engine"]:
    """Callable fixture to recreate models after any inline definitions of tables"""

    def _recreate_models() -> "Engine":
        from sciop.config import config

        engine = create_engine(str(config.sqlite_path))
        SQLModel.metadata.create_all(engine)
        return engine

    return _recreate_models


@pytest.fixture
def alembic_config() -> AlembicConfig:
    from sciop.db import get_alembic_config

    return get_alembic_config()
