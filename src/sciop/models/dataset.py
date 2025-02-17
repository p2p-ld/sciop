from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any, Optional, Self

from pydantic import field_validator, model_validator, TypeAdapter
from sqlmodel import Field, Relationship, SQLModel

from sciop.models.account import Account
from sciop.models.mixin import SearchableMixin, TableMixin, TableReadMixin
from sciop.models.tag import DatasetTagLink
from sciop.types import (
    AccessType,
    EscapedStr,
    IDField,
    InputType,
    MaxLenURL,
    Scarcity,
    ScrapeStatus,
    SlugStr,
    SourceType,
    Threat,
    ExternalIdentifierType,
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
        schema_extra={"json_schema_extra": {"autocomplete": "publisher"}},
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
    dataset_created_at: Optional[datetime] = Field(
        None,
        title="Dataset Creation Date",
        description="""
        Datetime when dataset was originally created in UTC. May be approximate or left blank.
        """,
    )
    dataset_updated_at: Optional[datetime] = Field(
        None,
        title="Dataset Last Updated",
        description="""
        Datetime when the dataset was last updated in UTC. May be approximate or left blank
        """,
    )
    source_type: SourceType = Field(
        "unknown",
        title="Source Type",
        description="""
    The protocol/technology needed to download the dataset.
    Use "web" if the dataset is an archive of websites themselves,
    and "http" if the dataset is some other raw data available via http download.
    """,
    )
    source_available: bool = Field(
        default=True,
        title="Source Available",
        description="""
        Whether the canonical source of this dataset is still available.
        """,
    )
    last_seen_at: Optional[datetime] = Field(
        default=None,
        title="Last Seen At",
        description="""
        If the dataset has been removed, the last time it was known to be available. 
        If the dataset is scheduled to be removed, 
        the time in the future where it is expected to be unavailable. 
        Otherwise, leave blank.
        Times should be in UTC.
        """,
    )
    source_access: AccessType = Field(
        default="unknown",
        title="Source Access",
        description="""
    How the canonical source can be accessed, whether it needs credentials
    or is intended to be public
    """,
    )
    scarcity: Scarcity = Field(
        default="unknown",
        title="Scarcity",
        description="""
    To prioritize scrapes, an estimate of the rarity of this dataset.
    Datasets that are likely to only exist in one or a few places are prioritized over
    those that are widely available.
    """,
    )
    threat: Threat = Field(
        default="unknown",
        title="Threat",
        description="""
    To prioritize scrapes, an estimate of how likely this dataset is likely to disappear
    in the immediate future. Datasets that are under direct threat due to the their nature
    or specific threats made against them are prioritized over those 
    for whom no specific threat exists.
    """,
    )


class Dataset(DatasetBase, TableMixin, SearchableMixin, table=True):
    __searchable__ = ["title", "slug", "publisher", "homepage", "description"]

    dataset_id: IDField = Field(None, primary_key=True)
    uploads: list["Upload"] = Relationship(back_populates="dataset")
    external_sources: list["ExternalSource"] = Relationship(back_populates="dataset")
    external_identifiers: list["ExternalIdentifier"] = Relationship(back_populates="dataset")
    urls: list["DatasetURL"] = Relationship(back_populates="dataset")
    tags: list["Tag"] = Relationship(
        back_populates="datasets",
        sa_relationship_kwargs={"lazy": "selectin"},
        link_model=DatasetTagLink,
    )
    account_id: Optional[int] = Field(default=None, foreign_key="account.account_id")
    account: Optional["Account"] = Relationship(back_populates="datasets")
    scrape_status: ScrapeStatus = "unknown"
    enabled: bool = False
    audit_log_target: list["AuditLog"] = Relationship(back_populates="target_dataset")



class DatasetCreate(DatasetBase):
    urls: list[MaxLenURL] = Field(
        title="URL(s)",
        description="""
        URL(s) to the direct download of the data, if public, 
        or any additional URLs associated with the dataset.
        One URL per line.
        If uploading a recursive web archive dump, only the top-level URL is needed.
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
    )
    tags: list[Annotated[SlugStr, Field(min_length=2, max_length=32)]] = Field(
        title="Tags",
        description="""
        Tags for this dataset. Use matching autocomplete values, when available.
        Enter as comma separated list or press enter to store a token.
        Only lowercase alphanumeric characters and `-` are allowed.
        Include as many tags as are applicable: topic, data type/file type,
        if this dataset is part of a collection (e.g. each dataset in NOAA's
        Fundamental Climate Data Records should be tagged with `fcdr`), etc.
        Tags are used to generate RSS feeds so people can reseed data that is important to them.
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.tokens}},
    )
    external_identifiers: list["ExternalIdentifierCreate"] = Field(default_factory=list)

    @field_validator("urls", "tags", mode="before")
    def split_lines(cls, value: str | list[str]) -> Optional[list[str]]:
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

    @field_validator("tags", "tags", mode="before")
    def split_commas(cls, value: str | list[str]) -> Optional[list[str]]:
        """Split lists of strings given as one entry per line"""
        if isinstance(value, str):
            if not value or value == "":
                return None
            value = value.split(",")

        # split any substrings, e.g. if comma-separated strings are used in
        # the token-input style of tag entry
        split_val = []
        for v in value:
            split_subvals = v.split(",")
            split_subvals = [subv.strip() for subv in split_subvals]
            split_val.extend(split_subvals)
        value = split_val

        # filter empty strings
        value = [v for v in value if v.strip()]

        # if left with an empty list, None
        if value:
            return value
        else:
            return None

    @field_validator("*", mode="before")
    def empty_strings_are_none(cls, value: Any) -> Any:
        """Forms sometimes submit input without anything as empty strings not None"""
        if value == "":
            value = None
        return value


class DatasetRead(DatasetBase, TableReadMixin):
    uploads: list["Upload"] = Field(default_factory=list)
    external_sources: list["ExternalSource"] = Field(default_factory=list)
    external_identifiers: list["ExternalIdentifier"] = Field(default_factory=list)
    urls: list["DatasetURL"] = Field(default_factory=list)
    tags: list["Tag"] = Field(default_factory=list)
    scrape_status: ScrapeStatus
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


class ExternalIdentifierBase(SQLModel):
    """
    Some additional, probably persistent identifier for a dataset
    """

    type: ExternalIdentifierType
    identifier: str

class ExternalIdentifier(ExternalIdentifierBase, TableMixin, table=True):
    __tablename__ = "external_identifier"

    external_identifier_id: IDField = Field(None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="dataset.dataset_id")
    dataset: Dataset = Relationship(back_populates="external_identifiers")


class ExternalIdentifierCreate(ExternalIdentifierBase):

    @field_validator("identifier", mode="before")
    def strip_whitespace(cls, val: str) -> str:
        return val.strip()

    @model_validator(mode="after")
    def validate_by_type(self) -> Self:
        """
        Apply additional validation from the annotation on the external identifier type
        """
        annotation = ExternalIdentifierType.__annotations__.get(self.type, None)
        if annotation is None:
            return self

        adapter = TypeAdapter(annotation)
        self.identifier = adapter.validate_python(self.identifier)
        return self
