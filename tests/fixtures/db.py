from typing import Callable

import pytest
from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy import Engine, create_engine
from sqlmodel import Session, SQLModel


@pytest.fixture(scope="session", autouse=True)
def create_tables(monkeypatch_session: "MonkeyPatch", monkeypatch_config: None) -> None:
    from sciop.config import config
    from sciop.db import create_tables

    engine = create_engine(str(config.sqlite_path))
    create_tables(engine)


@pytest.fixture
def session(monkeypatch: MonkeyPatch) -> Session:
    from sciop import db
    from sciop.api import deps
    from sciop.app import app
    from sciop.db import engine, get_session, maker
    from sciop.frontend import templates

    connection = engine.connect()

    # begin a non-ORM transaction
    trans = connection.begin()
    session = maker(bind=connection)

    def get_session_override() -> Session:
        yield session

    monkeypatch.setattr(db, "get_session", get_session_override)
    monkeypatch.setattr(templates, "get_session", get_session_override)
    monkeypatch.setattr(deps, "get_session", get_session_override)

    app.dependency_overrides[get_session] = get_session_override

    yield session

    session.close()
    trans.rollback()  # roll back to the SAVEPOINT
    connection.close()


@pytest.fixture
def recreate_models() -> Callable[[], "Engine"]:
    """Callable fixture to recreate models after any inline definitions of tables"""

    def _recreate_models() -> "Engine":
        from sciop.config import config

        engine = create_engine(str(config.sqlite_path))
        SQLModel.metadata.create_all(engine)
        return engine

    return _recreate_models
