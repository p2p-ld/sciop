"""add_rendered_html_fields

Revision ID: 44bd2fd2d4c0
Revises: e8b6da638a6f
Create Date: 2025-03-15 11:24:13.765344+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "44bd2fd2d4c0"
down_revision: Union[str, None] = "e8b6da638a6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _render_markdown_for_field(target: str, id_column: str, field: str) -> None:
    from sciop.services.markdown import render_markdown

    table = sa.Table(
        target,
        sa.MetaData(),
        sa.Column(id_column, sa.Integer(), key="id"),
        sa.Column(field, sa.String(), key="field"),
        sa.Column(field + "_html", sa.String(), key="field_html"),
    )
    conn = op.get_bind()
    results = conn.execute(
        sa.select(table.c.id, table.c.field).where(
            table.c.field.isnot(None) & table.c.field.isnot("")
        )
    ).fetchall()
    for id_, markdown in results:
        html = render_markdown(markdown)
        conn.execute(table.update().where(table.c.id == id_).values(field_html=html))


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("dataset_parts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "description_html",
                sqlmodel.sql.sqltypes.AutoString(length=8192),
                nullable=True,
            )
        )

    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "description_html",
                sqlmodel.sql.sqltypes.AutoString(length=8192),
                nullable=True,
            )
        )

    with op.batch_alter_table("uploads", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "method_html",
                sqlmodel.sql.sqltypes.AutoString(length=4096),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "description_html",
                sqlmodel.sql.sqltypes.AutoString(length=8192),
                nullable=True,
            )
        )
    # ### end Alembic commands ###

    _render_markdown_for_field("dataset_parts", "dataset_part_id", "description")
    _render_markdown_for_field("datasets", "dataset_id", "description")
    _render_markdown_for_field("uploads", "upload_id", "description")
    _render_markdown_for_field("uploads", "upload_id", "method")


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("uploads", schema=None) as batch_op:
        batch_op.drop_column("description_html")
        batch_op.drop_column("method_html")

    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.drop_column("description_html")

    with op.batch_alter_table("dataset_parts", schema=None) as batch_op:
        batch_op.drop_column("description_html")

    # ### end Alembic commands ###
