from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Column,
    Connection,
    MetaData,
    Select,
    String,
    Table,
    case,
    delete,
    event,
    exists,
    insert,
    inspect,
    literal,
    update,
)
from sqlalchemy.orm import Mapper, object_session
from sqlalchemy.orm.attributes import OP_BULK_REPLACE, AttributeEventToken, flag_dirty
from sqlmodel import Field, Relationship, SQLModel, select

from sciop.models.mixins import (
    EditableMixin,
    ListlikeMixin,
    SearchableMixin,
    SortableCol,
    SortMixin,
    TableMixin,
)
from sciop.types import IDField, MaxLenURL

if TYPE_CHECKING:
    from sciop.models import Dataset, Upload


class DatasetURLLink(TableMixin, EditableMixin, table=True):
    __tablename__ = "dataset_url_links"
    dataset_id: Optional[int] = Field(
        default=None, foreign_key="datasets.dataset_id", primary_key=True, index=True
    )
    url_id: Optional[int] = Field(
        default=None, foreign_key="urls.url_id", primary_key=True, index=True
    )


class UploadURLLink(TableMixin, EditableMixin, table=True):
    __tablename__ = "upload_url_links"
    upload_id: Optional[int] = Field(
        default=None, foreign_key="uploads.upload_id", primary_key=True, index=True
    )
    url_id: Optional[int] = Field(
        default=None, foreign_key="urls.url_id", primary_key=True, index=True
    )


class URL(ListlikeMixin, SearchableMixin, SortMixin, table=True):
    __tablename__ = "urls"
    __value_column_name__ = "url"
    __searchable__ = ["url"]
    __sortable__ = (SortableCol(name="url", title="URL"),)

    url_id: IDField = Field(default=None, primary_key=True)
    url: MaxLenURL = Field(unique=True)
    # links are only written by `BulkURLsMixin`
    datasets: list["Dataset"] = Relationship(
        back_populates="urls",
        link_model=DatasetURLLink,
        sa_relationship_kwargs={"viewonly": True},
    )
    uploads: list["Upload"] = Relationship(
        back_populates="urls",
        link_model=UploadURLLink,
        sa_relationship_kwargs={"viewonly": True},
    )

    @classmethod
    def search(cls, query: str) -> Select:
        """
        Urls that contain the query as typed come first, in lexicographic order,
        followed by the looser full text matches by rank.
        """
        matches = cls.search_statement(query).cte("matches")
        exact = cls.url.icontains(query, autoescape=True)
        return (
            select(cls)
            .join(matches, onclause=cls.url_id == matches.c.rowid)
            .order_by(exact.desc(), case((exact, 0), else_=matches.c.rank), cls.url)
        )


class BulkURLsMixin:
    """
    Write the links in a model's ``urls`` relationship with bulk statements during the flush.

    The ORM writes many-to-many links one row at a time, which is very slow for long
    lists of urls, so the ``urls`` relationship must be ``viewonly``,
    and assigned values (url strings or URL objects) are written here instead.
    Only assigning the whole list is supported: appending or removing raises a ``TypeError``.
    Until the flush, ``urls`` reads as empty.

    Bulk statements skip ORM events, so no edit history is recorded for the links.
    """

    @classmethod
    def __declare_last__(cls) -> None:
        event.listen(cls.urls, "bulk_replace", _capture_urls)
        for change in ("append", "append_wo_mutation", "remove"):
            event.listen(cls.urls, change, _forbid_partial_change)
        event.listen(cls, "after_insert", _write_urls)
        event.listen(cls, "after_update", _write_urls)


def _forbid_partial_change(target: SQLModel, value: Any, initiator: AttributeEventToken) -> None:
    # assigning the whole list also fires these, once for each item it replaces
    if initiator.op is not OP_BULK_REPLACE:
        raise TypeError(
            f"{type(target).__name__}.urls can only be assigned as a whole list, "
            "not appended to or removed from"
        )


def _capture_urls(target: SQLModel, values: list, initiator: Any) -> None:
    state = inspect(target)
    state.info["pending_urls"] = [u.url if isinstance(u, URL) else u for u in values]
    # empty the incoming list in place so the ORM never treats the urls as objects
    values.clear()
    # objects with no other changes still need to go through the flush
    if state.persistent:
        flag_dirty(target)


_staged_urls = Table(
    "staged_urls", MetaData(), Column("url", String, nullable=False), prefixes=["TEMPORARY"]
)


def _write_urls(mapper: Mapper, connection: Connection, target: SQLModel) -> None:
    """
    Optimized bulk routine for URL inserts:

    - Insert any urls that don't exist yet.
    - Insert a link to each url, or update its ``updated_at`` if it's already linked,
      so every link in the list is stamped with this save's time.
    - Delete the item's links that weren't stamped, i.e. urls no longer in the list.

    The urls are staged in a temporary table first, so that each step is a single
    statement over every url, rather than one statement per url:
    this means that the FTS index updates once per write rather than once per row.
    """
    urls = inspect(target).info.pop("pending_urls", None)
    if urls is None:
        return

    urls = list(dict.fromkeys(urls))
    prop = mapper.relationships["urls"]
    link_table = prop.secondary
    ((_, item_col),) = prop.synchronize_pairs
    ((_, url_col),) = prop.secondary_synchronize_pairs
    item_id = mapper.primary_key_from_instance(target)[0]
    # every link in the list is stamped with this time, then any links without it are deleted
    now = datetime.now(UTC)

    if urls:
        # Stage the urls in a temporary table
        _staged_urls.create(connection)
        connection.execute(insert(_staged_urls), [{"url": url} for url in urls])
        # insert the temporary table to the URLs table
        connection.execute(
            insert(URL.__table__).from_select(
                ["url"],
                select(_staged_urls.c.url).where(~exists().where(URL.url == _staged_urls.c.url)),
            )
        )

        # Convert the timestamp to sqlite's internal format once, rather than per-row
        to_db = link_table.c.updated_at.type.dialect_impl(connection.dialect).bind_processor(
            connection.dialect
        )
        stamp = literal(to_db(now))
        staged_url_ids = select(URL.url_id).join(_staged_urls, URL.url == _staged_urls.c.url)
        # stamp the links that already exist, then insert the ones that don't
        connection.execute(
            update(link_table)
            .where(item_col == item_id, url_col.in_(staged_url_ids))
            .values(updated_at=stamp)
        )
        connection.execute(
            insert(link_table).from_select(
                [item_col.key, url_col.key, "created_at", "updated_at"],
                select(literal(item_id), URL.url_id, stamp, stamp)
                .join(_staged_urls, URL.url == _staged_urls.c.url)
                .where(~exists().where(item_col == item_id, url_col == URL.url_id)),
            )
        )
        _staged_urls.drop(connection)

    connection.execute(
        delete(link_table).where(item_col == item_id, link_table.c.updated_at.is_distinct_from(now))
    )

    # the in-memory collection was emptied when the urls were assigned
    event.listen(
        object_session(target),
        "after_flush_postexec",
        lambda session, flush_context: session.expire(target, ["urls"]),
        once=True,
    )
