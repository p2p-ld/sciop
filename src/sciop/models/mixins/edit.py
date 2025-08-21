from dataclasses import dataclass
from datetime import UTC, datetime
from inspect import getmro
from logging import Logger
from typing import TYPE_CHECKING, Any, ClassVar, Generator, Iterable, Optional, Self, TypeVar, cast

import sqlalchemy as sqla
from annotated_types import MaxLen
from pydantic import ConfigDict
from sqlalchemy import Column, ColumnElement, ForeignKeyConstraint, Index, Table, event, inspect
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
from sqlmodel import Field, Session
from sqlmodel.main import RelationshipInfo

from sciop.config import get_config
from sciop.logging import init_logger
from sciop.models.base import SQLModel

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

    Inheriting classes *must* implement an ``update`` method that allows them to be updated
    from a SQLModel (usually the model's `create` variant) IF they are intended to be updated
    via user interaction. By default, the ``update`` method ignores any relations especially
    *-to-many relations, and this will almost certainly not work!

    TODO:
        There is an odd interaction between Editable and Moderable mixins w.r.t.
        collections of child objects -

        Moderable expects us not to delete objects, but instead mark them ``is_removed``

        Editable allows us to change collections of objects, store their history,
        and in particular remove items from collections.

        When an item is removed from a collection, its foreign key is nulled out by default,
        but Moderable expects us to instead preserve the information but mark it as ``is_removed``

        We should implement some custom behavior on collections for moderable items that
        intercepts their deletion or orphaning events, and then also exclude ``is_removed``
        items that nonetheless still have their foreign key intact linking them to the parent

        For now, we are handling this by excluding moderable relations from editing endpoints,
        so rather than removing a ``DatasetPart`` from a ``Dataset.parts`` collection,
        one needs to delete a ``DatasetPart`` individually as a moderable action.

        This should be more gracefully handled by the history classes so that we don't lose
        foreign keys that are necessary to identify an object, as well as not leaving
        items that will eventually violate uniqueness constraints in the original table.

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

    def update(self, session: "Session", new: SQLModel, commit: bool = False) -> Self:
        """Update a model in place"""
        updated = new.model_dump(exclude_unset=True)
        for key, value in updated.items():
            setattr(self, key, value)
        if commit:
            session.add(self)
            session.commit()
            session.refresh(self)
        return self

    @hybrid_method
    def editable_by(self, account: Optional["Account"] = None) -> bool:
        if account is None:
            return False
        return (
            self.account == account
            or account.has_scope("review")
            or (self.dataset_id and account.has_scope("edit", dataset_id=self.dataset_id))
        )

    @editable_by.inplace.expression
    @classmethod
    def _editable_by(cls, account: Optional["Account"] = None) -> ColumnElement[bool]:
        if hasattr(cls, "dataset_id"):
            return sqla.or_(
                cls.account == account,
                account.has_scope("review") == True,
                cls.account_scopes.any(scope="edit", account=account),
            )

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
    def history_cls(cls) -> type["EditableMixin"]:
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
            if not get_config().enable_versions:
                return
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
        return "version_created_at", "version_comment", "version_created_by", "version_is_deletion"

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
    account_id = session.info.get("current_account_id", None)

    obj_changed, attr = _check_if_changed(obj, obj_mapper, new=new)

    if not obj_changed and not deleted:
        obj.__editable_logger__.debug("Model is unchanged, not creating version")
        return

    hist = history_cls(
        **{
            **obj.model_dump(),
            "version_created_at": timestamp,
            "version_created_by": account_id,
            "version_is_deletion": deleted,
        }
    )
    session.add(hist)

    # create versions for any many-to-many link classes that don't receive normal ORM events
    for prop in obj_mapper.iterate_properties:
        _update_many_to_many(prop, obj, timestamp, account_id, flush_context, session, new=new)
        _update_one_to_many(prop, obj, timestamp, account_id, session)


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
    pydantic_fields = cls.__pydantic_fields__.copy()

    # clear max length constraints on fields - names are prefixed to avoid uniqueness constraints
    for field in pydantic_fields.values():
        if field.metadata:
            field.metadata = [i for i in field.metadata if not isinstance(i, MaxLen)]

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
                **pydantic_fields,
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
    for idx in list(table.indexes):
        idx.unique = False
        # indexes will be created for primary and foreign keys in _prepare_columns
        # but we do want to keep any other indexes that already exist on the parent table
        if any([c.foreign_keys or c.primary_key for c in idx.columns]):
            table.indexes.discard(idx)

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
            # primary key in parent table becomes foreign key in history table
            table.constraints.add(ForeignKeyConstraint([history_c], [orig_c]))
            history_c.index = True
            table.indexes.add(Index(f"ix_{table.name}_{history_c.name}", history_c))
        elif history_c.foreign_keys:
            table.indexes.add(Index(f"ix_{table.name}_{history_c.name}", history_c))

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
    cols["version_created_by"] = _MetaCol(
        col=Column(
            "version_created_by",
            sqla.Integer,
            ForeignKey("accounts.account_id"),
            default=None,
            nullable=True,
            info=history_meta,
        ),
        field=Field(default=None, nullable=True, foreign_key="accounts.account_id", index=True),
        annotation={"version_created_by": Optional[int]},
    )
    cols["version_is_deletion"] = _MetaCol(
        col=Column("version_is_deletion", sqla.Boolean, default=False, info=history_meta),
        field=Field(default=False, nullable=False),
        annotation={"version_is_deletion": bool},
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


def _should_update_many_to_many(
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


def _update_many_to_many(
    prop: _RelationshipDeclared,
    obj: EditableMixin,
    timestamp: datetime,
    account_id: int,
    flush_context: UOWTransaction,
    session: Session,
    new: bool = False,
) -> None:
    should_update, history, vals = _should_update_many_to_many(prop, obj, new=new)
    if not should_update:
        return

    # Create new history rows for each of the changed relationships
    link_model_cls = obj.__sqlmodel_relationships__[prop.key].link_model.history_cls()
    for v in vals:
        # if this was just created, it needs to be refreshed
        # ( which we can do because we prematurely finalized flush changes )
        if v in history.added:
            # if we are adding new stuff, it won't have its autogenerated primary keys yet
            # so we need to finalize the flush early and pray god does not see
            # since calling `flush_context.finalize_flush_changes` finalizes all items
            # in the session, which messes with detecting history changes,
            # we try to be a little more precise than that by just finalizing the object at hand.
            state_objs = [state for state in flush_context.states if state.obj() is v]
            if len(state_objs) > 0:
                state_obj = state_objs[0]
                session._register_persistent({state_obj})

            session.refresh(v)

        link_model_kwargs = _link_model_kwargs(v, obj, prop)
        link_model_kwargs["version_created_at"] = timestamp
        link_model_kwargs["version_created_by"] = account_id
        link_model_instance = link_model_cls(**link_model_kwargs)
        session.add(link_model_instance)
    for v in history.deleted:
        link_model_kwargs = _link_model_kwargs(v, obj, prop)
        link_model_kwargs["version_created_at"] = timestamp
        link_model_kwargs["version_created_by"] = account_id
        link_model_kwargs["version_is_deletion"] = True
        link_model_instance = link_model_cls(**link_model_kwargs)
        session.add(link_model_instance)


def _update_one_to_many(
    prop: _RelationshipDeclared,
    obj: EditableMixin,
    timestamp: datetime,
    account_id: int,
    session: Session,
) -> None:
    """
    need to explicitly add unchanged one-to-many children bc they're otherwise not updated
    so that we have a full version at a given version of the parent
    """

    # return if we're not a one-to-many
    if prop.key not in obj.__sqlmodel_relationships__:
        return
    relation = obj.__sqlmodel_relationships__[prop.key]
    if relation.link_model:
        return
    vals = getattr(obj, prop.key, None)
    if not vals or not isinstance(vals, list):
        return

    # return if we're not an editable object
    if not hasattr(vals[0], "__history_cls__"):
        return
    history_cls = vals[0].history_cls()

    # return if nothing has changed
    history = attributes.get_history(obj, prop.key, passive=attributes.PASSIVE_NO_INITIALIZE)
    if not history.has_changes():
        return

    for item in history.unchanged:
        history_instance = history_cls(
            **{
                **item.model_dump(),
                "version_created_at": timestamp,
                "version_created_by": account_id,
            },
        )
        session.add(history_instance)


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
