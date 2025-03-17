from dataclasses import dataclass
from datetime import UTC, datetime
from inspect import getmro
from logging import Logger
from typing import TYPE_CHECKING, Any, ClassVar, Generator, Iterable, Optional, Self, TypeVar, cast

import sqlalchemy as sqla
from pydantic import ConfigDict
from sqlalchemy import (
    Column,
    ColumnElement,
    ForeignKeyConstraint,
    Table,
    event,
    inspect,
)
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import (
    Mapper,
    RelationshipProperty,
    attributes,
    object_mapper,
    registry,
)
from sqlalchemy.orm.attributes import History
from sqlalchemy.orm.exc import UnmappedColumnError
from sqlalchemy.orm.relationships import _RelationshipDeclared
from sqlalchemy.orm.unitofwork import UOWTransaction
from sqlalchemy.sql.schema import ForeignKey
from sqlmodel import Field, Session, SQLModel
from sqlmodel.main import RelationshipInfo

from sciop.logging import init_logger

if TYPE_CHECKING:
    from sciop.models import Account

T = TypeVar("T")


class EditableMixin(SQLModel):
    """
    Mixin to create parallel tables to track edit history.

    In order for this to work, all joined tables must also be editable.

    Tables are constructed such that
    - existing primary keys are made into compound primary keys that include a timestamp
      that matches across any other updates within the session
    - foreign keys are added to map primary keys in the history table to the primary keys
      in the parent table
    """

    __table_args__ = {"sqlite_autoincrement": True}

    _history_table_configured: ClassVar[bool] = False
    __history_table__: ClassVar[Optional[Table]] = None
    __history_mapper__: ClassVar[Optional[Mapper]] = None
    __history_cls__: ClassVar[Optional[type["EditableMixin"]]] = None
    __is_history_cls__: ClassVar[bool] = False
    __editable_logger__: ClassVar[Logger] = False

    model_config = ConfigDict(
        ignored_types=(hybrid_method, hybrid_property), arbitrary_types_allowed=True
    )

    @hybrid_method
    def editable_by(self, account: Optional["Account"] = None) -> bool:
        if account is None:
            return False
        return self.account == account or account.has_scope("review")

    @editable_by.inplace.expression
    @classmethod
    def _editable_by(cls, account: Optional["Account"] = None) -> ColumnElement[bool]:
        if account is None:
            return sqla.false()
        return sqla.or_(cls.account == account, account.has_scope("review") == True)

    @classmethod
    def history_table(cls) -> Table:
        """
        A table that stores the versions of this object when edited
        """
        if cls.__history_table__ is None:
            raise AttributeError(
                "History table was not constructed, "
                "it must be created by an after_mapper_constructed event handler "
                "to be added to sqlalchemy's registry"
            )
        return cls.__history_table__

    @classmethod
    def history_cls(cls) -> "EditableMixin":
        if cls.__history_cls__ is None:
            raise AttributeError(
                "History class was not constructed, "
                "it must be created by an after_mapper_constructed event handler "
                "to be added to sqlalchemy's registry"
            )
        return cls.__history_cls__

    @classmethod
    def get_versions(cls, session: Session) -> list[Self]:
        """
        TODO: load versions. need to construct a query that loads matching versions across relations
        """
        raise NotImplementedError()

    @classmethod
    def latest(cls) -> Self:
        raise NotImplementedError()

    @classmethod
    def editable_objects(cls, iter_: Iterable[T]) -> Generator[T, None, None]:
        """Instances of editable objects within an iterable of objects"""
        for obj in iter_:
            if hasattr(obj, "__history_table__") and not obj.__is_history_cls__:
                yield obj

    @staticmethod
    def editable_session(session: Session) -> Session:
        @event.listens_for(session, "after_flush")
        def after_flush(session: Session, flush_context: UOWTransaction) -> None:
            timestamp = datetime.now(UTC)
            for obj in EditableMixin.editable_objects(session.new):
                create_version(obj, session, flush_context, timestamp, new=True)
            for obj in EditableMixin.editable_objects(session.dirty):
                create_version(obj, session, flush_context, timestamp)
            for obj in EditableMixin.editable_objects(session.deleted):
                create_version(obj, session, flush_context, timestamp, deleted=True)

        return session

    @classmethod
    def rebuild_history_models(cls, namespace: Optional[dict] = None) -> None:
        """
        Rebuild the history models of all subclasses

        Doesn't recurse through subclasses,
        Let's hope we don't have multiple inheritance of this (we shouldn't)
        """
        for subcls in cls.__subclasses__():
            subcls.__history_cls__.model_rebuild(_types_namespace=namespace)

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        insp: Mapper = inspect(cls, raiseerr=False)

        if not cls._history_table_configured:
            if insp is not None:
                _make_mapped_history_table(insp)
            else:

                @event.listens_for(cls, "after_mapper_constructed")
                def _mapper_constructed(mapper: Mapper, class_: type[EditableMixin]) -> None:
                    _make_mapped_history_table(mapper)

        cls.__editable_logger__ = init_logger(f"mixins.editable.{cls.__name__}")
        super().__init_subclass__(**kwargs)

    @classmethod
    def __history_meta_cols__(cls) -> tuple[str, ...]:
        """Columns that are added by the history table and not in the original object"""
        return "version_created_at", "version_comment"

    @classmethod
    def __history_table_name__(cls, tablename: Optional[str] = None) -> str:
        if tablename is None:
            tablename = cls.__tablename__
        return "__".join([tablename, "history"])


def create_version(
    obj: "EditableMixin",
    session: Session,
    flush_context: UOWTransaction,
    timestamp: datetime,
    deleted: bool = False,
    new: bool = False,
) -> None:
    """Create a new version for the passed object"""

    obj_mapper = object_mapper(obj)
    history_cls = obj.__history_mapper__.class_

    obj_changed, attr = _check_if_changed(obj, obj_mapper, new=new)

    if not obj_changed and not deleted:
        obj.__editable_logger__.debug("Model is unchanged, not creating version")
        return

    hist = history_cls(**{**obj.model_dump(), "version_created_at": timestamp})
    session.add(hist)

    # create versions for any many-to-many link classes that don't receive normal ORM events
    for prop in obj_mapper.iterate_properties:
        should_update, history, vals = _should_update_relationship(prop, obj, new=new)
        if not should_update:
            continue

        # if we are adding new stuff, it won't have its autogenerated primary keys yet
        # so we need to finalize the flush early and pray god does not see
        # calling this multiple times is fine, it becomes a no-op after the first
        flush_context.finalize_flush_changes()

        # Create new history rows for each of the changed relationships
        link_model_cls = obj.__sqlmodel_relationships__[prop.key].link_model.__history_cls__
        for v in vals:
            # if this was just created, it needs to be refreshed
            # ( which we can do because we prematurely finalized flush changes )
            if v in history.added:
                session.refresh(v)

            link_model_kwargs = _link_model_kwargs(v, obj, prop)
            link_model_kwargs["version_created_at"] = timestamp
            link_model_instance = link_model_cls(**link_model_kwargs)
            session.add(link_model_instance)


# --------------------------------------------------
# Table Creation
# --------------------------------------------------


@dataclass
class _MetaCol:
    col: Column
    field: Field
    annotation: dict[str, type]


def _make_mapped_history_table(mapper: Mapper) -> None:
    """
    Makes history table, adding it to the metadata object and storing in __history_table__.

    Top-level creation function for editable tables/classes :)
    """
    cls = mapper.class_
    if cls.__history_table_name__() in cls.__table__.metadata.tables:
        return
    elif cls.__history_table__ is not None:
        return
    elif cls._history_table_configured:
        return
    cls._history_mapper_configured = True

    # make extra cols to be added to table and orm class
    meta_cols = _make_meta_cols()

    # the table and history class have to be created separately and mapped imperatively
    # since sqlmodel is sorta abandoned and doesn't handle sqlalchemy declarative stuff well
    table, properties = _make_table(cls, mapper, meta_cols)
    history_cls = _make_orm_class(cls, mapper, meta_cols)

    # mapping connects the constructed ORM class to the table and instruments it
    reg = registry()
    reg.map_imperatively(history_cls, table, properties=properties, primary_key=table.primary_key)

    cls.__history_table__ = table
    cls.__history_cls__ = history_cls
    cls.__history_mapper__ = history_cls.__mapper__


def _make_table(
    cls: type[EditableMixin], mapper: Mapper, meta_cols: dict[str, _MetaCol]
) -> tuple[Table, dict[str, tuple]]:
    table = cls.__table__.to_metadata(
        mapper.local_table.metadata,
        name=cls.__history_table_name__(),
    )
    table = _prepare_table(table)
    table, properties = _prepare_columns(table, cls.__table__, mapper)

    # append meta cols to table
    for col in meta_cols.values():
        table.append_column(col.col)
    return table, properties


def _make_orm_class(
    cls: type[EditableMixin], mapper: Mapper, meta_cols: dict[str, _MetaCol]
) -> type[EditableMixin]:
    # Tell SQLModel to not process this as a table, we'll map it separately
    model_cfg = cls.model_config.copy()
    model_cfg["table"] = False

    annotations = _gather_annotations(cls, meta_cols)
    meta_fields = {k: col.field for k, col in meta_cols.items()}
    history_cls = cast(
        type[EditableMixin],
        type(
            cls.__name__ + "History",
            (mapper.base_mapper.class_,),
            {
                "__is_history_cls__": True,
                "__annotations__": annotations,
                "_history_table_configured": True,
                "model_config": model_cfg,
                **cls.__pydantic_fields__.copy(),
                **meta_fields,
            },
        ),
    )

    # delete mapped/instrumented fields from relations
    # these are incorrectly interpreted as pydantic fields,
    # but they are abstract and for sqlalchemy's use only
    cls_field_keys = list(history_cls.__pydantic_fields__.keys())
    for key in cls_field_keys:
        if key not in cls.__pydantic_fields__ and key not in cls.__history_meta_cols__():
            del history_cls.__pydantic_fields__[key]

    return history_cls


def _prepare_table(table: Table) -> Table:
    """Prepare history table by clearing constraints and etc."""
    table.sqlite_autoincrement = True
    for idx in table.indexes:
        if idx.name is not None:
            idx.name += "_history"
        idx.unique = False

    # clear any remaining non-fk constraints
    for const in list(table.constraints):
        if not isinstance(
            const,
            (ForeignKeyConstraint,),
        ):
            table.constraints.discard(const)
    return table


def _prepare_columns(
    table: Table, original_table: Table, mapper: Mapper
) -> tuple[Table, dict[str, tuple]]:
    """
    Prepare columns in history table - removing constraints,
    turning primary keys into fks
    """
    properties = {}
    for orig_c, history_c in zip(original_table.c, table.c):
        orig_c.info["history_copy"] = history_c
        history_c.unique = False
        history_c.default = history_c.server_default = None
        history_c.autoincrement = False

        if history_c.primary_key:
            # convert primary keys in primary tables to FKs
            history_c.primary_key = False
            parent_fk = ForeignKey(orig_c)
            history_c.foreign_keys.add(parent_fk)
            table.constraints.add(ForeignKeyConstraint([history_c], [orig_c]))

        orig_prop = mapper.get_property_by_column(orig_c)
        # carry over column re-mappings
        if len(orig_prop.columns) > 1 or orig_prop.columns[0].key != orig_prop.key:
            properties[orig_prop.key] = tuple(col.info["history_copy"] for col in orig_prop.columns)
    return table, properties


def _make_meta_cols() -> dict[str, _MetaCol]:
    """Make extra columns and fields for history tables"""
    history_meta = {"history_meta": True}
    cols = {}
    cols["version_created_at"] = _MetaCol(
        col=Column(
            "version_created_at",
            sqla.DateTime,
            server_default=sqla.func.datetime("now", "utc", "subsec"),
            info=history_meta,
            primary_key=True,
        ),
        field=Field(default=None, primary_key=True),
        annotation={"version_created_at": datetime},
    )
    cols["version_comment"] = _MetaCol(
        col=Column(
            "version_comment",
            sqla.Text(length=4096),
            default=None,
            info=history_meta,
            nullable=True,
        ),
        field=Field(default=None, nullable=True, max_length=4096),
        annotation={"version_comment": Optional[str]},
    )

    return cols


def _gather_annotations(
    cls: type[EditableMixin], meta_cols: dict[str, _MetaCol]
) -> dict[str, type]:
    """Gather annotations for the created ORM class"""
    annotations = {}

    # Annotations from base classes
    for base in reversed(getmro(cls)):
        if not hasattr(base, "__annotations__"):
            continue
        annotations.update(base.__annotations__.copy())
    annotations.update(cls.__annotations__.copy())

    # Annotations from extra columns
    for col in meta_cols.values():
        annotations.update(col.annotation)
    return annotations


# --------------------------------------------------
# Version creation
# --------------------------------------------------


def _check_if_changed(
    obj: EditableMixin, obj_mapper: Mapper, new: bool = False
) -> tuple[bool, dict]:
    attr = {}

    obj_state = attributes.instance_state(obj)
    history_mapper = obj.__history_mapper__
    obj_changed = False

    # if creating a new object, we're definitely storing a version of the object
    if new:
        obj_changed = True

    for om, hm in zip(obj_mapper.iterate_to_root(), history_mapper.iterate_to_root()):

        if hm.single:
            continue

        for hist_col in hm.local_table.c:
            if "history_meta" in hist_col.info:
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

    # if haven't decided to update yet, check relations for changes
    if not obj_changed:
        for prop in obj_mapper.iterate_properties:
            if (
                isinstance(prop, RelationshipProperty)
                and attributes.get_history(
                    obj, prop.key, passive=attributes.PASSIVE_NO_INITIALIZE
                ).has_changes()
            ):
                obj_changed = True
                break

    return obj_changed, attr


def _should_update_relationship(
    prop: _RelationshipDeclared, obj: EditableMixin, new: bool = False
) -> tuple[bool, Optional[History], Optional[list[Any]]]:
    """
    Check if a relationship property should also get a new version.

    This is primarily to handle versioned link models that don't get normal ORM events

    Checks that a property...
    - is a relationship
    - is multivalued
    - currently has values
    - has been changed
    - has a version table/is editable
    """
    if not isinstance(prop, RelationshipProperty) or not isinstance(
        vals := getattr(obj, prop.key, None), list
    ):
        return False, None, None

    if len(vals) == 0:
        return False, None, vals

    history = attributes.get_history(obj, prop.key, passive=attributes.PASSIVE_NO_INITIALIZE)
    if not history.has_changes() and not new:
        return False, history, vals

    # they make it very difficult to access the link model with sqlalchemy,
    # yet here we are...
    rel_info: RelationshipInfo = obj.__sqlmodel_relationships__[prop.key]
    if not rel_info.link_model or not hasattr(rel_info.link_model, "__history_cls__"):
        return False, history, vals

    return True, history, vals


def _link_model_kwargs(v: SQLModel, obj: EditableMixin, prop: _RelationshipDeclared) -> dict:
    """
    Link models get kwargs from both the object and the property,
    and it's not altogether obvious which are which, so we have to do some ~ introspection ~
    """
    kwargs = {}
    # local side
    local_col_keys = [col.key for col in prop.local_columns]
    kwargs.update({k: getattr(obj, k) for k in local_col_keys})
    # remote side
    remote_col = [col for col in prop.remote_side if col.key not in local_col_keys]
    kwargs.update({col.key: getattr(v, col.key) for col in remote_col})
    return kwargs
