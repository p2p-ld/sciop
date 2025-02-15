from typing import TYPE_CHECKING, Annotated, Any, Optional

from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel

from sciop.models.account import Account
from sciop.models.mixin import SearchableMixin, TableMixin, TableReadMixin
from sciop.models.tag import DatasetTagLink
from sciop.types import (
    EscapedStr,
    IDField,
    InputType,
    MaxLenURL,
    Priority,
    SlugStr,
    SourceType,
    Status,
)

if TYPE_CHECKING:
    from sciop.models import AuditLog, Tag, Upload


class DatasetBase(SQLModel):
    title: EscapedStr = Field(
        title="Title",
        description="""
    Human readable name for dataset. 
    Match the title given by the source as closely as possible.
    """,
        min_length=3,
        max_length=512,
    )
    slug: SlugStr = Field(
        title="Dataset Slug",
        description="""
    Short, computer readable name for dataset.
    The acronym or abbreviation of the dataset name, e.g. for the NOAA
    "Fundamental Climate Data Record - Mean Layer Temperature NOAA"
    use "fcdr-mlt-noaa". Converted to a slugified string.
    """,
        unique=True,
        index=True,
        min_length=2,
        max_length=128,
    )
    publisher: EscapedStr = Field(
        title="Publisher",
        description="""
    The agency, organization, author, group, publisher, etc. that is associated with the dataset.
    Please use a canonical acronym/abbreviation form of the name when possible,
    using the autocompleted values if any correct matches are listed.
    """,
        max_length=256,
    )
    homepage: Optional[MaxLenURL] = Field(
        None,
        title="Homepage",
        description="""
    The index/landing page that describes this dataset
    (but isn't necessarily the direct link to the data itself), if any. 
    """,
    )
    description: Optional[EscapedStr] = Field(
        None,
        title="Description",
        description="""
    Additional information about the dataset.
    """,
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
        max_length=4096,
    )
    priority: Priority = Field("unknown", title="Priority")
    priority_comment: Optional[EscapedStr] = Field(
        None,
        title="Priority Comment",
        description="""
    Additional information about the priority of preserving this dataset,
    if it is especially endangered or likely to be tampered with in the short term.
    """,
        schema_extra={"input_type": InputType.textarea},
        max_length=1024,
    )
    source: SourceType = Field(
        "unknown",
        title="Source Type",
        description="""
    The protocol/technology needed to download the dataset.
    Use "web" if the dataset is an archive of websites themselves,
    and "http" if the dataset is some other raw data available via http download.
    """,
    )


class Dataset(DatasetBase, TableMixin, SearchableMixin, table=True):
    __searchable__ = ["title", "slug", "publisher", "homepage", "description"]

    dataset_id: IDField = Field(None, primary_key=True)
    uploads: list["Upload"] = Relationship(back_populates="dataset")
    external_sources: list["ExternalSource"] = Relationship(back_populates="dataset")
    urls: list["DatasetURL"] = Relationship(back_populates="dataset")
    tags: list["Tag"] = Relationship(
        back_populates="datasets",
        sa_relationship_kwargs={"lazy": "selectin"},
        link_model=DatasetTagLink,
    )
    account_id: Optional[int] = Field(default=None, foreign_key="account.account_id")
    account: Optional["Account"] = Relationship(back_populates="datasets")
    status: Status = "todo"
    enabled: bool = False
    audit_log_target: list["AuditLog"] = Relationship(back_populates="target_dataset")


class DatasetCreate(DatasetBase):
    urls: list[MaxLenURL] = Field(
        title="URL(s)",
        description="""
        URL(s) to the direct download of the data, if public.
        One URL per line.
        If uploading a recursive web archive dump (source type == web), 
        only the top-level URL is needed.
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
    )
    tags: list[Annotated[SlugStr, Field(min_length=2, max_length=32)]] = Field(
        title="Tags",
        description="""
        Tags for this dataset. One tag per line. 
        Only lowercase alphanumeric characters and `-` are allowed.
        Include as many tags as are applicable: topic, data type/file type,
        if this dataset is part of a collection (e.g. each dataset in NOAA's
        Fundamental Climate Data Records should be tagged with `fcdr`), etc.
        Tags are used to generate RSS feeds so people can reseed data that is important to them.
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
    )

    @field_validator("urls", "tags", mode="before")
    def split_strings(cls, value: str | list[str]) -> Optional[list[str]]:
        """Split lists of strings given as one entry per line"""
        if isinstance(value, str):
            if not value or value == "":
                return None
            value = value.splitlines()
        elif isinstance(value, list) and len(value) == 1:
            if "\n" in value[0]:
                value = value[0].splitlines()
            elif value[0] == "":
                return None

        # filter empty strings
        value = [v for v in value if v.strip()]
        return value

    @field_validator("*", mode="before")
    def empty_strings_are_none(cls, value: Any) -> Any:
        """Forms sometimes submit input without anything as empty strings not None"""
        if value == "":
            value = None
        return value


class DatasetRead(DatasetBase, TableReadMixin):
    uploads: list["Upload"] = Field(default_factory=list)
    external_sources: list["ExternalSource"] = Field(default_factory=list)
    urls: list["DatasetURL"] = Field(default_factory=list)
    tags: list["Tag"] = Field(default_factory=list)
    status: Status
    enabled: bool


class DatasetURL(SQLModel, table=True):
    __tablename__ = "dataset_url"

    dataset_url_id: IDField = Field(default=None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="dataset.dataset_id")
    dataset: Optional[Dataset] = Relationship(back_populates="urls")
    url: MaxLenURL


class ExternalSourceBase(SQLModel):
    """An external source for this dataset"""

    source: EscapedStr = Field(
        description="The name of the group or person who provides the dataset",
        max_length=256,
    )
    url: MaxLenURL = Field(description="Link to the external source", max_length=512)
    description: EscapedStr = Field(
        description="Additional information about the completeness, accuracy, etc. "
        "of the external source",
        max_length=4096,
    )


class ExternalSource(ExternalSourceBase, TableMixin, table=True):
    __tablename__ = "external_source"

    external_source_id: IDField = Field(None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="dataset.dataset_id")
    dataset: Dataset = Relationship(back_populates="external_sources")
    account_id: Optional[int] = Field(default=None, foreign_key="account.account_id")
    account: Optional[Account] = Relationship(back_populates="external_submissions")
