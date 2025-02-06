from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional, Self

from sqlalchemy import event
from sqlmodel import Field, Session, SQLModel, select, text

if TYPE_CHECKING:
    from sqlalchemy import Table
    from sqlalchemy.engine import Connection
    from sqlalchemy.sql.expression import Select


class TableMixin(SQLModel):
    """Mixin to add base elements to all tables"""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)},
    )


class TableReadMixin(SQLModel):
    """
    Mixin to add base elements to the read version of all tables
    """

    id: int
    created_at: datetime
    updated_at: datetime


class SearchableMixin(SQLModel):
    """
    Mixin that makes a sqlmodel class full text searchable using external content tables
    https://sqlite.org/fts5.html#external_content_tables

    Inspired in part by:
    https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-xvi-full-text-search
    """

    __searchable__: list[str] = None
    """
    List of columns that should be added to the full text search table 
    """

    @classmethod
    def __fts_table_name__(cls) -> str:
        return "__".join([cls.__tablename__, "search"])

    @classmethod
    def search(cls, query: str, session: Session) -> list[Self]:
        """Do a full text search!"""
        return session.exec(cls.search_statement(query)).all()

    @classmethod
    def search_statement(cls, query: str) -> "Select":
        """Construct a select statement to do a full text search without executing"""
        text_stmt = text(
            f"SELECT rowid as id, * FROM {cls.__fts_table_name__()} WHERE {cls.__fts_table_name__()} MATCH :query ORDER BY rank;"  # noqa: E501
        ).bindparams(query=query)
        return select(cls).from_statement(text_stmt)

    @classmethod
    def register_events(cls) -> None:
        """
        # FIXME: make this happen on class declaration with a decorator
        """
        event.listen(cls.__table__, "after_create", cls.after_create)

    @classmethod
    def after_create(cls, target: "Table", connection: Connection, **kwargs: Any) -> None:
        """Create a matching full text search table with triggers to keep it updates"""
        if not cls.__searchable__:
            return

        # table_name = "__".join([target.name, "search"])
        table_name = cls.__fts_table_name__()
        col_names = ", ".join(cls.__searchable__)
        new_names = ", ".join([f"new.{cname}" for cname in cls.__searchable__])
        old_names = ", ".join([f"old.{cname}" for cname in cls.__searchable__])
        # ruff: noqa: E501
        create_stmt = text(
            f"""
            CREATE VIRTUAL TABLE {table_name} USING fts5({col_names}, content={target.name}, content_rowid=id);
            """
        )
        trigger_insert = text(
            f"""
            CREATE TRIGGER {target.name}_ai AFTER INSERT ON {target.name} BEGIN
              INSERT INTO {table_name}(rowid, {', '.join(cls.__searchable__)}) VALUES (new.id, {new_names});
            END;
            """
        )
        trigger_delete = text(
            f"""
            CREATE TRIGGER {target.name}_ad AFTER DELETE ON {target.name} BEGIN
              INSERT INTO {table_name}({table_name}, rowid, {col_names}) VALUES('delete', old.id, {old_names});
            END;
            """
        )
        trigger_update = text(
            f"""
            CREATE TRIGGER {target.name}_au AFTER UPDATE ON {target.name} BEGIN
              INSERT INTO {table_name}({table_name}, rowid, {col_names}) VALUES('delete', old.id, {old_names});
              INSERT INTO {table_name}(rowid, {col_names}) VALUES (new.id, {new_names});
            END;
            """
        )
        connection.execute(create_stmt)
        connection.execute(trigger_insert)
        connection.execute(trigger_delete)
        connection.execute(trigger_update)


class TestSearchability(SearchableMixin, TableMixin, table=True):
    __searchable__ = ["title", "description"]
    title: str
    description: str


#
