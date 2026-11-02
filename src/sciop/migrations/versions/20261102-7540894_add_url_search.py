"""add-url-search

Revision ID: 75408948af0f
Revises: 53e10f088ece
Create Date: 2026-11-02 01:59:23.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from sciop import models

# revision identifiers, used by Alembic.
revision: str = "75408948af0f"
down_revision: Union[str, None] = "53e10f088ece"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    models.URL.after_create(models.URL.__table__, conn)
    table_name = models.URL.fts_table_name()
    conn.execute(sa.text(f"INSERT INTO {table_name}({table_name}) VALUES('rebuild');"))


def downgrade() -> None:
    for trigger_name in models.URL.fts_trigger_names():
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name};")
    op.execute(f"DROP TABLE IF EXISTS {models.URL.fts_table_name()};")
