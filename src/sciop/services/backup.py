"""
Backup routines for sciop!

Two kinds:
- internal, complete backups for being able to roll back
- external, censored backups for propagating metadata and inter-instance resiliency
  (not implemented yet)
"""

from datetime import UTC, datetime

from sqlalchemy import text


async def create_db_backup() -> None:
    """
    Create an internal db backup to the `config.backup.dir`
    """
    from sciop.config import config
    from sciop.db import get_session
    from sciop.logging import init_logger

    logger = init_logger("jobs.backup")

    backup_stem = config.db.stem if config.db is not None else "db"
    backup_name = (
        "_".join([backup_stem, datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")]) + ".sqlite"
    )
    backup_path = config.backups.dir / backup_name
    logger.info(f"Backing up database to {backup_path}")

    try:
        with next(get_session()) as session:
            session.execute(text("VACUUM INTO :path"), {"path": str(backup_path)})

    except Exception as e:
        logger.error(f"Could not backup database: {e}")
