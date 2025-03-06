import contextlib
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, Generator, Optional, Self, TypeVar, get_origin

import sqlalchemy as sqla
from pydantic import ConfigDict
from sqlalchemy import (
    CheckConstraint,
    Column,
    ColumnElement,
    Connection,
    ForeignKeyConstraint,
    Table,
    event,
    inspect,
    select,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import Mapper, attributes, object_mapper, object_session
from sqlalchemy.orm.exc import UnmappedColumnError
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlmodel import Field, Session, SQLModel, select, text

from sciop.types import IDField, InputType, UTCDateTime

if TYPE_CHECKING:
    from sqlalchemy import Connection, Table, TextClause
    from sqlalchemy.sql.expression import Select
    from sqlmodel.main import FieldInfo

    from sciop.models import Account

T = TypeVar("T")


class TableMixin(SQLModel):
    """Mixin to add base elements to all tables"""

    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)},
    )

    model_config = ConfigDict(ignored_types=(hybrid_method, hybrid_property))

    @property
    def id(self) -> int:
        """
        The value of the primary key, `table_id` property.
        """
        for name, field in self.model_fields.items():
            try:
                if field.annotation is IDField or IDField in get_origin(field.annotation):
                    return getattr(self, name)
            except TypeError:
                continue
        raise AttributeError("No IDField found")


class TableReadMixin(SQLModel):
    """
    Mixin to add base elements to the read version of all tables
    """

    created_at: UTCDateTime
    updated_at: UTCDateTime


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

    _fts_table: ClassVar[Table] = None

    @classmethod
    def primary_key_column(cls) -> str:
        """
        Name of the column that is the primary key, i.e. is an IDField
        (Assuming there is only one)
        """
        for name, field in cls.model_fields.items():
            field: FieldInfo
            if getattr(field, "primary_key", False) is True:
                return name
        raise ValueError("No primary key found")

    @classmethod
    def fts_table(cls) -> Table:
        """Virtual table for full text search"""
        if cls._fts_table is None:
            cols = [Column(colname) for colname in cls.__searchable__]
            cls._fts_table = Table(
                cls.__fts_table_name__(),
                cls.metadata,
                Column("rowid"),
                *cols,
            )
        return cls._fts_table

    @classmethod
    def __fts_table_name__(cls) -> str:
        return "__".join([cls.__tablename__, "search"])

    @classmethod
    def search(cls, query: str, session: Session) -> list[Self]:
        """
        Find model instances that match the provided query
        This convenience method should generally be avoided, as it returns all matches
        and its text statement makes it impossible/tricky to combine with other queries,
        but it is a bit more efficient than the `in` clause in the normal search_statement
        """

        text_stmt = text(
            f"SELECT rowid as {cls.primary_key_column()}, * FROM {cls.__fts_table_name__()} "  # noqa: S608 - confirmed no sqli
            f"WHERE {cls.__fts_table_name__()} MATCH :q ORDER BY rank;"
        ).bindparams(q=query)
        stmt = select(cls).from_statement(text_stmt)
        return session.exec(stmt).all()

    @classmethod
    def search_statement(cls, query: str) -> "Select":
        """
        Search query statement on the full text search table that selects
        only the row IDs, so that the full object can be retrieved in a subsequent query,
        probably as a subquery.

        Examples:

            .. code-block:: python

                query = select(Example
                    ).where(
                        Example.some_column == True
                    ).filter(
                        Example.id.in_(Example.search_statement(query))
                    )

        """
        table = cls.fts_table()
        if len(query) < 3:
            query = query + "*"
            where_clause = text(f"{cls.__fts_table_name__()} = :query").bindparams(query=query)
        else:
            where_clause = text(f"{cls.__fts_table_name__()} = :query").bindparams(query=query)

        return (
            select(table.c.rowid.label(cls.primary_key_column()))
            .where(where_clause)
            .order_by(text("rank"))
        )

    @classmethod
    def count_statement(cls, query: str) -> "TextClause":
        """Select statement to count number of search results"""
        return text(
            f"SELECT count(*) FROM {cls.__fts_table_name__()} WHERE {cls.__fts_table_name__()} MATCH :q;"  # noqa: S608 - confirmed no sqli
        ).bindparams(q=query)

    @classmethod
    def register_events(cls) -> None:
        """
        # FIXME: make this happen on class declaration with a decorator
        """
        event.listen(cls.__table__, "after_create", cls.after_create)

    @classmethod
    def after_create(cls, target: "Table", connection: "Connection", **kwargs: Any) -> None:
        """
        Create a matching full text search table with triggers to keep it updated

        Uses an external content table - https://sqlite.org/fts5.html#external_content_and_contentless_tables
        and the ``trigram`` tokenizer to support subtoken queries

        These are definitely string interpolations in sql text clauses,
        but none of the interpolated values are from user input, all are derived from the model class
        """
        if not cls.__searchable__:
            return

        table_name = cls.__fts_table_name__()
        col_names = ", ".join(cls.__searchable__)
        new_names = ", ".join(
            [f"new.{cname}" for cname in [cls.primary_key_column()] + cls.__searchable__]
        )
        old_names = ", ".join(
            [f"old.{cname}" for cname in [cls.primary_key_column()] + cls.__searchable__]
        )
        # ruff: noqa: E501
        create_stmt = text(
            f"""
            CREATE VIRTUAL TABLE {table_name} USING fts5({col_names}, content={target.name}, content_rowid={cls.primary_key_column()}, tokenize='trigram');
            """
        )
        trigger_insert = text(
            f"""  
            CREATE TRIGGER {target.name}_ai AFTER INSERT ON {target.name} BEGIN
              INSERT INTO {table_name}(rowid, {', '.join(cls.__searchable__)}) VALUES ({new_names});
            END;
            """  # noqa: S608 - confirmed no sqli
        )
        trigger_delete = text(
            f"""
            CREATE TRIGGER {target.name}_ad AFTER DELETE ON {target.name} BEGIN
              INSERT INTO {table_name}({table_name}, rowid, {col_names}) VALUES('delete', {old_names});
            END;
            """
        )
        trigger_update = text(
            f"""
            CREATE TRIGGER {target.name}_au AFTER UPDATE ON {target.name} BEGIN
              INSERT INTO {table_name}({table_name}, rowid, {col_names}) VALUES('delete', {old_names});
              INSERT INTO {table_name}(rowid, {col_names}) VALUES ({new_names});
            END;
            """  # noqa: S608 - confirmed no sqli
        )
        try:
            connection.execute(create_stmt)
        except OperationalError as e:
            if "already exists" not in str(e):
                raise e

        connection.execute(trigger_insert)
        connection.execute(trigger_delete)
        connection.execute(trigger_update)


class EnumTableMixin(SQLModel):
    """Enum table mixin for method for ensuring all enum values exist"""

    __enum_column_name__: ClassVar[str] = None
    """Column that has the enum values for which rows should be created"""

    @classmethod
    def enum_class(cls) -> StrEnum:
        """Get the enum itself used in the enum column"""
        return cls.model_fields[cls.__enum_column_name__].annotation

    @classmethod
    def ensure_enum_values(cls, session: Session) -> None:
        if cls.__enum_column_name__ is None:
            raise ValueError("__enum_column_name__ must be declared for EnumTableMixins")

        enum = cls.enum_class()
        for item in enum:
            stmt = select(cls).where(getattr(cls, cls.__enum_column_name__) == item.value)
            existing_enum_row = session.exec(stmt).first()
            if not existing_enum_row:
                db_item = cls(**{cls.__enum_column_name__: item.value})
                session.add(db_item)

        session.commit()

    @classmethod
    def get_item(cls, item: str | StrEnum, session: Session) -> Self:
        """Get the row corresponding to this enum item"""
        if isinstance(item, str) and sys.version_info < (3, 12):
            if item not in cls.enum_class().__members__:
                raise KeyError(f"No such item {item} exists in {cls.enum_class()}")
        elif item not in cls.enum_class():
            raise KeyError(f"No such item {item} exists in {cls.enum_class()}")

        return session.exec(
            select(cls).where(getattr(cls, cls.__enum_column_name__) == item)
        ).first()


class ListlikeMixin(SQLModel):
    """
    Mixin for models that are many-to-many joined to "primary" models,
    like tags, urls, etc. where the same tag or url is expected to be re-used many times
    """

    __value_column_name__: ClassVar[str] = None

    @classmethod
    def get_item(cls, value: str, session: Session) -> Self:
        """Get the row corresponding to the value of this item"""
        if cls.__value_column_name__ is None:
            raise ValueError("__value_column__ must be declared for ListlikeMixins")

        return session.exec(
            select(cls).where(getattr(cls, cls.__value_column_name__) == value)
        ).first()


class ModerableMixin(SQLModel):
    """
    Common columns/properties among moderable objects
    """

    is_approved: bool = Field(
        False,
        description="Whether this item has been reviewed and is now visible",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
    )
    is_removed: bool = Field(
        False,
        description="Whether the item has been, for all practical purposes, deleted.",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
    )

    model_config = ConfigDict(ignored_types=(hybrid_method, hybrid_property))

    # TODO: https://github.com/fastapi/sqlmodel/issues/299#issuecomment-2223569400
    @hybrid_property
    def is_visible(self) -> bool:
        """Whether the dataset should be displayed and included in feeds"""
        return self.is_approved and not self.is_removed

    @is_visible.inplace.expression
    @classmethod
    def _is_visible(cls) -> ColumnElement[bool]:
        return sqla.and_(cls.is_approved == True, cls.is_removed == False)

    @hybrid_property
    def needs_review(self) -> bool:
        """Whether a dataset needs to be reviewed"""
        return not self.is_approved and not self.is_removed

    @needs_review.inplace.expression
    @classmethod
    def _needs_review(cls) -> ColumnElement[bool]:
        return sqla.and_(cls.is_approved == False, cls.is_removed == False)

    @hybrid_method
    def visible_to(self, account: Optional["Account"] = None) -> bool:
        """Whether this item is visible to the given account"""
        if account is None:
            return self.is_visible
        if self.is_visible:
            return True
        elif self.is_removed:
            return False
        elif hasattr(self, "account") and self.account == account:
            return True
        else:
            return account.has_scope("review")

    @visible_to.inplace.expression
    @classmethod
    def _visible_to(cls, account: Optional["Account"] = None) -> ColumnElement[bool]:
        if account is None:
            return cls._is_visible

        if hasattr(cls, "account"):
            return sqla.and_(
                cls.is_removed == False,
                sqla.or_(
                    cls.is_visible == True,
                    account.has_scope("review") == True,
                    cls.account == account,
                ),
            )
        else:
            return sqla.and_(
                cls.is_removed == False,
                sqla.or_(cls.is_visible == True, account.has_scope("review") == True),
            )

    @hybrid_method
    def removable_by(self, account: Optional["Account"] = None) -> bool:
        if account is None:
            return False
        return self.account == account or account.has_scope("review")

    @removable_by.inplace.expression
    @classmethod
    def _removable_by(cls, account: Optional["Account"] = None) -> ColumnElement[bool]:
        if account is None:
            return sqla.false()
        return sqla.or_(cls.account == account, account.has_scope("review") == True)


class EditableMixin(SQLModel):
    """
    Mixin to create parallel tables to track edit history
    """

    __table_args__ = {"sqlite_autoincrement": True}

    _edit_table_configured: ClassVar[bool] = False
    __edit_table__: ClassVar[Optional[Table]] = None
    __edit_mapper__: ClassVar[Optional[Mapper]] = None

    @classmethod
    def edit_table(cls) -> Table:
        """
        adapted from
        https://docs.sqlalchemy.org/en/20/_modules/examples/versioned_history/history_meta.html
        """
        if cls.__edit_table__ is None:
            cls._make_edit_table()
        return cls.__edit_table__

    @staticmethod
    def _make_edit_table(mapper: Mapper):
        """
        Makes edit table, adding it to the metadata object and storing in __edit_table__
        """
        cls = mapper.class_
        cls.__table__: Table
        if cls.__edit_table_name__() in cls.__table__.metadata.tables:
            return
        elif cls.__edit_table__ is not None:
            return
        elif cls._edit_table_configured:
            return
        cls._history_mapper_configured = True

        properties = {}

        table = cls.__table__.to_metadata(
            mapper.local_table.metadata,
            name=cls.__edit_table_name__(),
        )
        table.sqlite_autoincrement = True
        for idx in table.indexes:
            if idx.name is not None:
                idx.name += "_edits"
            idx.unique = False

        for orig_c, edit_c in zip(cls.__table__.c, table.c):
            orig_c.info["edit_copy"] = edit_c
            edit_c.unique = False
            edit_c.default = edit_c.server_default = None
            edit_c.autoincrement = False
            edit_c.primary_key = False

            orig_prop = mapper.get_property_by_column(orig_c)
            # carry over column re-mappings
            if len(orig_prop.columns) > 1 or orig_prop.columns[0].key != orig_prop.key:
                properties[orig_prop.key] = tuple(
                    col.info["history_copy"] for col in orig_prop.columns
                )

        for const in list(table.constraints):
            if not isinstance(const, (ForeignKeyConstraint,)):
                table.constraints.discard(const)

        edit_meta = {"edit_meta": True}

        table.append_column(
            Column(
                cls.__edit_pk_col_name__(),
                sqla.Integer,
                primary_key=True,
                nullable=True,
                # autoincrement=True,
                info=edit_meta,
            )
        )

        table.append_column(
            Column(
                "edit_created_at", sqla.DateTime, default=lambda: datetime.now(UTC), info=edit_meta
            )
        )
        # bases = mapper.base_mapper.class_.__bases__
        # edit_cls = type(
        #     cls.__name__ + "Edits",
        #     bases,
        #     {
        #         "__table__": table,
        #         "_edit_table_configured": True,
        #         "__mapper_args__": {"properites": properties},
        #     },
        # )
        # reg = registry()
        # reg.map_imperatively(edit_cls, table)

        cls.__edit_table__ = table

        # cls.__edit_cls__ = edit_cls

        # cls.__edit_mapper__ = edit_cls.__mapper__

    @classmethod
    def __edit_table_name__(cls) -> str:
        return "__".join([cls.__tablename__, "edits"])

    @classmethod
    def __edit_pk_col_name__(cls) -> str:
        return "_".join([cls.__tablename__, "edit_id"])

    @classmethod
    def __edit_meta_cols__(cls) -> tuple[str, ...]:
        """Columns that are added by the edit table and not in the original object"""
        return cls.__edit_pk_col_name__(), "edit_created_at"

    @classmethod
    def _register_events(cls):

        @event.listens_for(cls, "after_insert")
        def _after_insert(mapper, connection, target):
            cls.create_version(target, connection)

        @event.listens_for(cls, "after_update")
        def _after_update(mapper, connection, target):
            is_modified = object_session(target).is_modified(target, include_collections=False)
            if is_modified:
                cls.create_version(target, connection)

    @staticmethod
    def create_version(obj: "EditableMixin", connection: Connection):
        # inst = obj.__edit_cls__(**obj.model_dump())
        # session.add(inst)
        connection.execute(
            sqla.insert(obj.__edit_table__),
            obj.model_dump(),
        )
        # pdb.set_trace()

    @classmethod
    def create_version_sqla(cls, obj: "EditableMixin", session: Session, deleted: bool = False):
        """Create a"""

        obj_mapper = object_mapper(obj)
        history_mapper = obj.__edit_mapper__
        history_cls = history_mapper.class_

        obj_state = attributes.instance_state(obj)

        attr = {}

        obj_changed = False

        for om, hm in zip(obj_mapper.iterate_to_root(), history_mapper.iterate_to_root()):
            if hm.single:
                continue

            for hist_col in hm.local_table.c:
                if "edit_meta" in hist_col.info:
                    continue

                obj_col = om.local_table.c[hist_col.key]

                # get the value of the
                # attribute based on the MapperProperty related to the
                # mapped column.  this will allow usage of MapperProperties
                # that have a different keyname than that of the mapped column.
                try:
                    prop = obj_mapper.get_property_by_column(obj_col)
                except UnmappedColumnError:
                    # in the case of single table inheritance, there may be
                    # columns on the mapped table intended for the subclass only.
                    # the "unmapped" status of the subclass column on the
                    # base class is a feature of the declarative module.
                    continue

                # expired object attributes and also deferred cols might not
                # be in the dict.  force it to load no matter what by
                # using getattr().
                if prop.key not in obj_state.dict:
                    getattr(obj, prop.key)

                a, u, d = attributes.get_history(obj, prop.key)

                if d:
                    attr[prop.key] = d[0]
                    obj_changed = True
                elif u:
                    attr[prop.key] = u[0]
                elif a:
                    # if the attribute had no value.
                    attr[prop.key] = a[0]
                    obj_changed = True

        if not obj_changed:
            # not changed, but we have relationships.  OK
            # check those too
            for prop in obj_mapper.iterate_properties:
                if (
                    isinstance(prop, RelationshipProperty)
                    and attributes.get_history(
                        obj, prop.key, passive=attributes.PASSIVE_NO_INITIALIZE
                    ).has_changes()
                ):
                    for p in prop.local_columns:
                        if p.foreign_keys:
                            obj_changed = True
                            break
                    if obj_changed is True:
                        break

        if not obj_changed and not deleted:
            return

        attr["version"] = obj.version
        hist = history_cls()
        for key, value in attr.items():
            setattr(hist, key, value)
        session.add(hist)
        obj.version += 1

    @classmethod
    def editable_objects(cls, iter_: Iterable[T]) -> Generator[T, None, None]:
        """Instances of editable objects within an iterable of objects"""
        for obj in iter_:
            if hasattr(obj, "__edit_table__"):
                yield obj

    @staticmethod
    def editable_session(session):
        @event.listens_for(session, "before_flush")
        def before_flush(session, flush_context, instances):
            for obj in EditableMixin.editable_objects(session.dirty):
                EditableMixin.create_version(obj, session)
            # for obj in versioned_objects(session.deleted):
            #     EditableMixin.create_version(obj, session, deleted=True)

        return session

    @classmethod
    def __init_subclass__(cls, **kwargs) -> None:
        insp: Mapper = inspect(cls, raiseerr=False)

        if not cls._edit_table_configured:
            cls._register_events()

        if insp is not None:
            # cls.__edit_mapper__ = insp
            cls._make_edit_table(insp)
        else:

            @event.listens_for(cls, "after_mapper_constructed")
            def _mapper_constructed(mapper, class_):
                # class_.__edit_mapper__ = mapper
                class_._make_edit_table(mapper)

        super().__init_subclass__(**kwargs)


class _FriedolinType(StrEnum):
    friedolin = "friedolin"


class _Friedolin(SQLModel, table=True):
    __tablename__ = "friedolin"
    friedolin: _FriedolinType = Field(
        "friedolin",
        primary_key=True,
        unique=True,
        sa_column_args=[
            CheckConstraint(text("friedolin = 'friedolin'"), name="the_friedolin_constraint")
        ],
    )


@event.listens_for(_Friedolin.__table__, "after_create")
def _make_friedolin(target: Table, connection: Connection, **kwargs: Any) -> None:
    with contextlib.suppress(Exception):
        # this can fail and we literally don't care
        connection.execute(target.insert().values(friedolin="friedolin"))
