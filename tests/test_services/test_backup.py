from sqlalchemy import Engine, MetaData
from sqlmodel import create_engine

from sciop.services.backup import create_db_backup


def _dump_db(engine: Engine) -> dict:
    """https://stackoverflow.com/a/47308472/13113166"""
    meta = MetaData()
    meta.reflect(bind=engine)
    result = {}
    with engine.connect() as conn:
        for table in meta.sorted_tables:
            result[table.name] = [dict(row._mapping) for row in conn.execute(table.select())]
    return result


async def test_db_backup(monkeypatch, tmp_path, default_db):
    from sciop.config import config
    from sciop.db import get_engine

    monkeypatch.setattr(config.backups, "dir", tmp_path)

    await create_db_backup()

    backup = list(tmp_path.glob("*.sqlite"))
    assert len(backup) == 1
    backup = backup[0]
    backup_engine = create_engine(f"sqlite:///{backup.resolve()}")

    backup_dump = _dump_db(backup_engine)
    src_dump = _dump_db(get_engine())
    # ensure these aren't just empty...
    assert backup_dump
    assert src_dump
    # pytest does a deep diff automatically
    assert backup_dump == src_dump
