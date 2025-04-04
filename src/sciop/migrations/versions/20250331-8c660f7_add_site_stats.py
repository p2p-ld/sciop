"""add-site-stats

Revision ID: 8c660f76bc3e
Revises: e5376c65e837
Create Date: 2025-03-31 22:51:00.556803+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c660f76bc3e"
down_revision: Union[str, None] = "e5376c65e837"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "site_stats",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("n_seeders", sa.Integer(), nullable=True),
        sa.Column("n_downloaders", sa.Integer(), nullable=True),
        sa.Column("n_datasets", sa.Integer(), nullable=False),
        sa.Column("n_uploads", sa.Integer(), nullable=False),
        sa.Column("n_files", sa.Integer(), nullable=False),
        sa.Column("total_size", sa.Integer(), nullable=False),
        sa.Column("total_capacity", sa.Integer(), nullable=True),
        sa.Column("site_stats_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("site_stats_id", name=op.f("pk_site_stats_site_stats_id")),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("site_stats")
    # ### end Alembic commands ###
