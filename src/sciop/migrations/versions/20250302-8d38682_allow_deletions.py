"""allow-deletions

Revision ID: 8d38682c9b50
Revises: 8514cd884e91
Create Date: 2025-03-02 08:35:50.777958+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d38682c9b50"
down_revision: Union[str, None] = "8514cd884e91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename enabled
    with op.batch_alter_table("uploads", schema=None) as batch_op:
        batch_op.alter_column("enabled", new_column_name="is_approved")
    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.alter_column("enabled", new_column_name="is_approved")
    with op.batch_alter_table("dataset_parts", schema=None) as batch_op:
        batch_op.alter_column("enabled", new_column_name="is_approved")

    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.add_column(sa.Column("target_dataset_part_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_audit_log_target_dataset_part_id_dataset_parts"),
            "dataset_parts",
            ["target_dataset_part_id"],
            ["dataset_part_id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("dataset_parts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_removed", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.alter_column(
            "part_slug",
            existing_type=sa.VARCHAR(length=256),
            type_=sqlmodel.sql.sqltypes.AutoString(length=269),
            existing_nullable=False,
        )

    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_removed", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.alter_column(
            "slug",
            existing_type=sa.VARCHAR(length=128),
            type_=sqlmodel.sql.sqltypes.AutoString(length=141),
            existing_nullable=False,
        )

    with op.batch_alter_table("files_in_torrent", schema=None) as batch_op:
        batch_op.drop_constraint("fk_files_in_torrent_torrent_id_torrent_files", type_="foreignkey")
        batch_op.create_foreign_key(
            batch_op.f("fk_files_in_torrent_torrent_id_torrent_files"),
            "torrent_files",
            ["torrent_id"],
            ["torrent_file_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("trackers_in_torrent", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_trackers_in_torrent_torrent_id_torrent_files", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_trackers_in_torrent_torrent_id_torrent_files"),
            "torrent_files",
            ["torrent_id"],
            ["torrent_file_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("uploads", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_removed", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    with op.batch_alter_table("uploads", schema=None) as batch_op:
        batch_op.alter_column("is_approved", new_column_name="enabled")
    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.alter_column("is_approved", new_column_name="enabled")
    with op.batch_alter_table("dataset_parts", schema=None) as batch_op:
        batch_op.alter_column("is_approved", new_column_name="enabled")

    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("uploads", schema=None) as batch_op:
        batch_op.drop_column("is_removed")

    with op.batch_alter_table("trackers_in_torrent", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_trackers_in_torrent_torrent_id_torrent_files"), type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_trackers_in_torrent_torrent_id_torrent_files",
            "torrent_files",
            ["torrent_id"],
            ["torrent_file_id"],
        )

    with op.batch_alter_table("files_in_torrent", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_files_in_torrent_torrent_id_torrent_files"), type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_files_in_torrent_torrent_id_torrent_files",
            "torrent_files",
            ["torrent_id"],
            ["torrent_file_id"],
        )

    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.alter_column(
            "slug",
            existing_type=sqlmodel.sql.sqltypes.AutoString(length=141),
            type_=sa.VARCHAR(length=128),
            existing_nullable=False,
        )
        batch_op.drop_column("is_removed")

    with op.batch_alter_table("dataset_parts", schema=None) as batch_op:
        batch_op.alter_column(
            "part_slug",
            existing_type=sqlmodel.sql.sqltypes.AutoString(length=269),
            type_=sa.VARCHAR(length=256),
            existing_nullable=False,
        )
        batch_op.drop_column("is_removed")

    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_audit_log_target_dataset_part_id_dataset_parts"), type_="foreignkey"
        )
        batch_op.drop_column("target_dataset_part_id")

    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.drop_column("is_suspended")

    # ### end Alembic commands ###
