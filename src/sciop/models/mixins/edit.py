import pdb
from datetime import UTC, datetime
from typing import ClassVar, Generator, Iterable, Optional, TypeVar, Self
from inspect import getmro

from copy import copy
import sqlalchemy as sqla
from pydantic import ConfigDict
from pydantic._internal._namespace_utils import MappingNamespace
from sqlalchemy import (
    Column,
    Connection,
    PrimaryKeyConstraint,
    ForeignKeyConstraint,
    Table,
    event,
    inspect,
)
from sqlalchemy.orm import (
    Mapper,
    RelationshipProperty,
    attributes,
    object_mapper,
    object_session,
    registry,
)
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.orm.exc import UnmappedColumnError
from sqlmodel import Session, SQLModel, Field
from sqlmodel.main import RelationshipInfo

T = TypeVar("T")


class EditableMixin(SQLModel):
    """
    Mixin to create parallel tables to track edit history.

    In order for this to work, all joined tables must also be editable.

    Tables are constructed such that
    - a new primary key is generated like `{tablename}_history_id`
    - existing primary keys in the main table are replaced by
      foreign keys pointing to the main table
    - existing foreign keys in the main table are replaced by
      foreign keys pointing to columns in the history tables of those tables

    As such, we expect all relations to *also* be versioned.
    If they are not versioned, e.g. a tags table where "versions" of a tag would be meaningless,
    then one must add the name of that table to the __no_history_tables__ list below.

    This is an ugly hack due to the order of operations when mapping classes -
    at the time we are constructing tables here, the tables we are referencing may not have
    been constructed yet. So we have no way of passing information from the table itself.
    """

    __no_history_tables__: ClassVar[str] = ("tags", "accounts", "trackers")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    __table_args__ = {"sqlite_autoincrement": True}

    _history_table_configured: ClassVar[bool] = False
    __history_table__: ClassVar[Optional[Table]] = None
    __history_mapper__: ClassVar[Optional[Mapper]] = None
    __history_cls__: ClassVar[Optional[type["EditableMixin"]]] = None
    __is_history_cls__: ClassVar[bool] = False

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

        # if cls.__name__ == "Dataset":
        #     pdb.set_trace()

        # clear existing constraints, recreate them below

        # new_fk_cols = []
        for orig_c, history_c in zip(cls.__table__.c, table.c):
            orig_c.info["history_copy"] = history_c
            history_c.unique = False
            history_c.default = history_c.server_default = None
            history_c.autoincrement = False

            # if history_c.foreign_keys:
            #     # new fk column that refers to the history table
            #     # the referent table may not have been mapped yet! so we can't access it directly
            #     # instead operate on string representations
            #     for fk in list(history_c.foreign_keys):
            #         table_name = fk.target_fullname.split(".")[0]
            #         if table_name not in cls.__no_history_tables__:
            #             fk_table_name = cls.__history_table_name__(table_name)
            #             fk_col_name = cls.__history_pk_col_name__(table_name)
            #             new_fk_cols.append(
            #                 Column(
            #                     fk_col_name,
            #                     sqla.Integer,
            #                     ForeignKey(f"{fk_table_name}.{fk_col_name}"),
            #                 )
            #             )

            if history_c.primary_key:
                # FK to the main tables primary key

                history_c.primary_key = False
                parent_fk = ForeignKey(orig_c)
                history_c.foreign_keys.add(parent_fk)
                table.constraints.add(ForeignKeyConstraint([history_c], [orig_c]))

            orig_prop = mapper.get_property_by_column(orig_c)
            # carry over column re-mappings
            if len(orig_prop.columns) > 1 or orig_prop.columns[0].key != orig_prop.key:
                properties[orig_prop.key] = tuple(
                    col.info["history_copy"] for col in orig_prop.columns
                )
        # if table.name in ("datasets__history", "dataset_tag_links__history"):
        #     pdb.set_trace()
        # add new foreign keys created in previous step
        # for new_fk in new_fk_cols:
        #
        #     table.append_column(new_fk)

        # referenced_col = next(iter(new_fk.foreign_keys)).target_fullname
        # table.constraints.add(ForeignKeyConstraint([new_fk], [referenced_col]))

        # clear any remaining constraints, particularly PKs, recreate below
        for const in list(table.constraints):
            if not isinstance(
                const,
                (ForeignKeyConstraint,),
            ):
                table.constraints.discard(const)

        history_meta = {"history_meta": True}

        # table.primary_key = PrimaryKeyConstraint()
        # table.append_column(
        #     Column(
        #         cls.__history_pk_col_name__(),
        #         sqla.Integer,
        #         primary_key=True,
        #         nullable=False,
        #         autoincrement=True,
        #         info=history_meta,
        #     )
        # )

        table.append_column(
            Column(
                "version_created_at",
                sqla.DateTime,
                # default=datetime.now(),
                server_default=sqla.func.datetime("now", "utc", "subsec"),
                info=history_meta,
                primary_key=True,
            )
        )

        model_cfg = cls.model_config.copy()
        model_cfg["table"] = False
        pk_field = Field(default=None, primary_key=True)
        pk_field.__annotations__ = {int}
        created_at_field = Field(default=None)
        created_at_field.__annotations__ = {datetime}
        annotations = {}
        for base in reversed(getmro(cls)):
            if not hasattr(base, "__annotations__"):
                continue
            annotations.update(base.__annotations__.copy())
        annotations.update(cls.__annotations__.copy())

        history_cls = type(
            cls.__name__ + "History",
            (mapper.base_mapper.class_,),
            {
                "_history_table_configured": True,
                "__is_history_cls__": True,
                "model_config": model_cfg,
                # cls.__history_pk_col_name__(): pk_field,
                "version_created_at": created_at_field,
                "__annotations__": {
                    **annotations,
                    # cls.__history_pk_col_name__(): int,
                    "version_created_at": datetime,
                },
                **cls.__pydantic_fields__.copy(),
            },
        )

        # delete mapped keys
        cls_field_keys = list(history_cls.__pydantic_fields__.keys())
        for key in cls_field_keys:
            if key not in cls.__pydantic_fields__ and key not in cls.__history_meta_cols__():
                del history_cls.__pydantic_fields__[key]

        reg = registry()
        reg.map_imperatively(
            history_cls, table, properties=properties, primary_key=table.primary_key
        )

        cls.__history_table__ = table

        cls.__history_cls__ = history_cls

        cls.__history_mapper__ = history_cls.__mapper__

    @classmethod
    def __history_table_name__(cls, tablename: Optional[str] = None) -> str:
        if tablename is None:
            tablename = cls.__tablename__
        return "__".join([tablename, "history"])

    @classmethod
    def __history_pk_col_name__(cls, tablename: Optional[str] = None) -> str:
        if tablename is None:
            tablename = cls.__tablename__
        return "_".join([tablename, "history_id"])

    @classmethod
    def __history_meta_cols__(cls) -> tuple[str, ...]:
        """Columns that are added by the history table and not in the original object"""
        return cls.__history_pk_col_name__(), "version_created_at"

    # @classmethod
    # def _register_events(cls):
    #
    #     @event.listens_for(cls, "after_insert")
    #     def _after_insert(mapper, connection, target):
    #         cls.create_version(target, connection)
    #
    #     @event.listens_for(cls, "after_update")
    #     def _after_update(mapper, connection, target):
    #         is_modified = object_session(target).is_modified(target, include_collections=False)
    #         if is_modified:
    #             cls.create_version(target, connection)

    @staticmethod
    def create_version(obj: "EditableMixin", session: Session):
        inst = obj.__history_cls__.model_validate(obj)
        # pdb.set_trace()
        session.add(inst)
        # connection.execute(
        #     sqla.insert(obj.__history_table__),
        #     obj.model_dump(),
        # )
        # pdb.set_trace()

    @classmethod
    def latest(cls) -> Self:
        pass

    @classmethod
    def create_version_sqla(
        cls, obj: "EditableMixin", session: Session, flush_context, deleted: bool = False
    ):
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

        # if not obj_changed:
        # not changed, but we have relationships.  OK
        # check those too
        for prop in obj_mapper.iterate_properties:

            # try:
            #     if isinstance(prop, RelationshipProperty) and prop.key == "tags":
            #
            #         history = attributes.get_history(obj, prop.key)
            # except:
            #     pdb.set_trace()

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
            print(f"unchanged {obj}")
            return

        version_timestamp = datetime.now(UTC)
        hist = history_cls(**{**obj.model_dump(), "version_created_at": version_timestamp})
        # set all the relationship attrs to Nones - they are InstrumentedAttributes not actual defaults
        # FIXME: move this to model creation time, fix the defaults
        # for prop in obj_mapper.iterate_properties:
        #     if isinstance(prop, RelationshipProperty):
        #         # make a fake empty version of the instrumented adapter class
        #         pdb.set_trace()
        #         instrumented_attr = type(getattr(obj, prop.key))()
        #         instrumented_attr._sa_adapter = copy(getattr(obj, prop.key)._sa_adapter)
        #
        #         setattr(hist, prop.key, instrumented_attr)

        # for key, value in attr.items():
        #     # print(key, value)
        #     setattr(hist, key, value)
        session.add(hist)
        # create versions for any *-to-many classes that wouldn't get caught in the session
        # as object to update
        # flattened into a maybe weird looking set of continue statements to avoid computing
        # history if we don't have to and also avoid being indented to hell
        # i'll clean this up later
        for prop in obj_mapper.iterate_properties:
            if not isinstance(prop, RelationshipProperty) or not isinstance(
                vals := getattr(obj, prop.key, None), list
            ):
                continue
            if len(vals) == 0:
                continue
            history = attributes.get_history(
                obj, prop.key, passive=attributes.PASSIVE_NO_INITIALIZE
            )
            if not history.has_changes():
                continue
            # if we are adding new stuff, it won't have its autogenerated primary keys yet
            # so we need to finalize the flush early and pray god does not see
            flush_context.finalize_flush_changes()

            # they make it very difficult to access the link model with sqlalchemy, yet here we are...
            rel_info: RelationshipInfo = obj.__sqlmodel_relationships__[prop.key]
            if not rel_info.link_model or not hasattr(rel_info.link_model, "__history_cls__"):
                continue

            # finally...
            history_cls = rel_info.link_model.__history_cls__
            for v in vals:
                # if this was just created, it needs to be refreshed
                # ( which we can do because we prematurely finalized flush changes)
                if v in history.added:
                    session.refresh(v)

                history_kwargs = {}

                # local side
                local_col_keys = [col.key for col in prop.local_columns]
                history_kwargs.update({k: getattr(obj, k) for k in local_col_keys})
                # remote side
                # FIXME: extremely fragile
                remote_col = [col for col in prop.remote_side if col.key not in local_col_keys]
                history_kwargs.update({col.key: getattr(v, col.key) for col in remote_col})
                # remote_key = list(list(prop.remote_side)[1].foreign_keys)[0].column.key
                # history_kwargs[remote_key] = getattr(v, remote_key)

                # we have to do this whacky shit because the history class receives
                # the InstrumentAttributes as defaults, rather than the actual default values lmao
                # if we ever fix that, change this.
                # update: fixed that, now need to clean this up
                history_instance = history_cls(
                    **{
                        **rel_info.link_model(**history_kwargs).model_dump(),
                        "version_created_at": version_timestamp,
                    }
                )
                # if v.tag == "newtag":
                #     pdb.set_trace()
                session.add(history_instance)

    @classmethod
    def editable_objects(cls, iter_: Iterable[T]) -> Generator[T, None, None]:
        """Instances of editable objects within an iterable of objects"""
        for obj in iter_:
            if hasattr(obj, "__history_table__"):
                yield obj

    @staticmethod
    def editable_session(session):
        @event.listens_for(session, "after_flush")
        def after_flush(session, flush_context):
            # pdb.set_trace()
            for obj in EditableMixin.editable_objects(session.dirty):
                EditableMixin.create_version_sqla(obj, session, flush_context)
            for obj in EditableMixin.editable_objects(session.deleted):
                EditableMixin.create_version_sqla(obj, session, flush_context, deleted=True)

        return session

    @classmethod
    def __init_subclass__(cls, **kwargs) -> None:
        insp: Mapper = inspect(cls, raiseerr=False)

        if not cls._history_table_configured:

            if insp is not None:
                # cls.__history_mapper__ = insp
                cls._make_history_table(insp)
            else:

                @event.listens_for(cls, "after_mapper_constructed")
                def _mapper_constructed(mapper, class_):
                    # class_.__history_mapper__ = mapper
                    class_._make_history_table(mapper)

        super().__init_subclass__(**kwargs)

    @classmethod
    def rebuild_history_models(cls, namespace: Optional[dict] = None):
        """
        Rebuild the history models of all subclasses

        Let's hope we don't have multiple inheritance of this (we shouldn't)
        """
        for subcls in cls.__subclasses__():
            subcls.__history_cls__.model_rebuild(_types_namespace=namespace)

