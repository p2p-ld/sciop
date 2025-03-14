from datetime import UTC, datetime
from typing import ClassVar, Generator, Iterable, Optional, TypeVar

import sqlalchemy as sqla
from sqlalchemy import Column, Connection, ForeignKeyConstraint, Table, event, inspect
from sqlalchemy.orm import (
    Mapper,
    RelationshipProperty,
    attributes,
    object_mapper,
    object_session,
    registry,
)
from sqlalchemy.orm.exc import UnmappedColumnError
from sqlmodel import Session, SQLModel

T = TypeVar("T")


class EditableMixin(SQLModel):
    """
    Mixin to create parallel tables to track edit history
    """

    __table_args__ = {"sqlite_autoincrement": True}

    _history_table_configured: ClassVar[bool] = False
    __history_table__: ClassVar[Optional[Table]] = None
    __history_mapper__: ClassVar[Optional[Mapper]] = None

    @classmethod
    def history_table(cls) -> Table:
        """
        adapted from
        https://docs.sqlalchemy.org/en/20/_modules/examples/versioned_history/history_meta.html
        """
        if cls.__history_table__ is None:
            cls._make_history_table()
        return cls.__history_table__

    @staticmethod
    def _make_history_table(mapper: Mapper):
        """
        Makes history table, adding it to the metadata object and storing in __history_table__
        """
        cls = mapper.class_
        cls.__table__: Table
        if cls.__history_table_name__() in cls.__table__.metadata.tables:
            return
        elif cls.__history_table__ is not None:
            return
        elif cls._history_table_configured:
            return
        cls._history_mapper_configured = True

        properties = {}

        table = cls.__table__.to_metadata(
            mapper.local_table.metadata,
            name=cls.__history_table_name__(),
        )
        table.sqlite_autoincrement = True
        for idx in table.indexes:
            if idx.name is not None:
                idx.name += "_history"
            idx.unique = False

        for orig_c, history_c in zip(cls.__table__.c, table.c):
            orig_c.info["history_copy"] = history_c
            history_c.unique = False
            history_c.default = history_c.server_default = None
            history_c.autoincrement = False
            history_c.primary_key = False

            orig_prop = mapper.get_property_by_column(orig_c)
            # carry over column re-mappings
            if len(orig_prop.columns) > 1 or orig_prop.columns[0].key != orig_prop.key:
                properties[orig_prop.key] = tuple(
                    col.info["history_copy"] for col in orig_prop.columns
                )

        for const in list(table.constraints):
            if not isinstance(const, (ForeignKeyConstraint,)):
                table.constraints.discard(const)

        history_meta = {"history_meta": True}

        table.append_column(
            Column(
                cls.__history_pk_col_name__(),
                sqla.Integer,
                primary_key=True,
                nullable=True,
                # autoincrement=True,
                info=history_meta,
            )
        )

        table.append_column(
            Column(
                "version_created_at", sqla.DateTime, default=lambda: datetime.now(UTC), info=history_meta
            )
        )

        model_cfg = cls.model_config.copy()
        model_cfg["table"] = False
        history_cls = type(
            cls.__name__ + "History",
            (mapper.base_mapper.class_,),
            {
                "_history_table_configured": True,
                "model_config": model_cfg,
            },
        )

        reg = registry()
        reg.map_imperatively(
            history_cls, table, properties=properties, primary_key=cls.__history_pk_col_name__()
        )

        cls.__history_table__ = table

        cls.__history_cls__ = history_cls

        cls.__history_mapper__ = history_cls.__mapper__

    @classmethod
    def __history_table_name__(cls) -> str:
        return "__".join([cls.__tablename__, "history"])

    @classmethod
    def __history_pk_col_name__(cls) -> str:
        return "_".join([cls.__tablename__, "history_id"])

    @classmethod
    def __history_meta_cols__(cls) -> tuple[str, ...]:
        """Columns that are added by the history table and not in the original object"""
        return cls.__history_pk_col_name__(), "version_created_at"

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
            sqla.insert(obj.__history_table__),
            obj.model_dump(),
        )
        # pdb.set_trace()

    @classmethod
    def create_version_sqla(cls, obj: "EditableMixin", session: Session, deleted: bool = False):
        """Create a"""

        obj_mapper = object_mapper(obj)
        history_mapper = obj.__history_mapper__
        history_cls = history_mapper.class_

        obj_state = attributes.instance_state(obj)

        attr = {}

        obj_changed = False

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
            if hasattr(obj, "__history_table__"):
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

        if not cls._history_table_configured:
            cls._register_events()

        if insp is not None:
            # cls.__history_mapper__ = insp
            cls._make_history_table(insp)
        else:

            @event.listens_for(cls, "after_mapper_constructed")
            def _mapper_constructed(mapper, class_):
                # class_.__history_mapper__ = mapper
                class_._make_history_table(mapper)

        super().__init_subclass__(**kwargs)
