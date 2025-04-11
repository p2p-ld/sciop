"""recalculate total size of torrents

Revision ID: 22c913bf49a0
Revises: f65409701c98
Create Date: 2025-04-11 06:28:21.659483+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "22c913bf49a0"
down_revision: Union[str, None] = "f65409701c98"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sciop.config import config
    from pathlib import Path

    table = sa.Table(
        "torrent_files",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), key="id"),
        sa.Column("files", sa.String(), key="files"),
        # sa.Column("total_size", sa.Integer(), key="size"),
    )

    conn = op.get_bind()
    results = conn.execute(
        sa.select(table.c.id, table.c.files, table.c.size)
    ).fetchall()

    for id_, _files in results:
        files = [Path.joinpath(config.torrent_dir, file).stat().st_size for file in _files]
        size = sum(files)
        conn.execute(table.update().where(table.c.id == id_).values(size=size))



def downgrade() -> None:
    pass
