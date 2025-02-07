import re
from enum import StrEnum
from typing import TYPE_CHECKING, Optional, Self
from urllib.parse import urljoin

from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel, Session, select

from sciop.config import config
from sciop.models.account import Account
from sciop.models.mixin import SearchableMixin, TableMixin, TableReadMixin

if TYPE_CHECKING:
    from sciop.models import TorrentFile


class Priority(StrEnum):
    unknown = "unknown"
    low = "low"
    medium = "medium"
    high = "high"


class SourceType(StrEnum):
    unknown = "unknown"
    web = "web"
    http = "http"
    ftp = "ftp"
    s3 = "s3"


class Status(StrEnum):
    todo = "todo"
    claimed = "claimed"
    completed = "completed"


class InputType(StrEnum):
    text = "text"
    textarea = "textarea"


class DatasetBase(SQLModel):
    title: str = Field(
        title="Title",
        description="""
    Human readable name for dataset. 
    Match the title given by the source as closely as possible.
    """,
    )
    slug: str = Field(
        title="Dataset Slug",
        description="""
    Short, computer readable name for dataset.
    The acronym or abbreviation of the dataset name, e.g. for the NOAA
    "Fundamental Climate Data Record - Mean Layer Temperature NOAA"
    use "fcdr-mlt-noaa"
    """,
        unique=True,
        index=True,
    )
    agency: str = Field(
        title="Agency",
        description="""
    The Agency or Organization that is associated with the dataset.
    Please use a canonical acronym/abbreviation form of the name when possible,
    using the autocompleted values if any correct matches are listed.
    """,
    )
    homepage: Optional[str] = Field(
        None,
        title="Homepage",
        description="""
    (Optional) The index/landing page that describes this dataset
    (but isn't necessarily the direct link to the data itself), if any. 
    """,
    )
    description: Optional[str] = Field(
        None,
        title="Description",
        description="""
    (Optional) Additional information about the dataset.
    """,
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
    )
    priority: Priority = Field("unknown", title="Priority")
    priority_comment: Optional[str] = Field(
        None,
        title="Priority Comment",
        description="""
    (Optional) Additional information about the priority of preserving this dataset,
    if it is especially endangered or likely to be tampered with in the short term.
    """,
        schema_extra={"input_type": InputType.textarea},
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
    __searchable__ = ["title", "slug", "agency", "homepage", "description"]
    instances: list["DatasetInstance"] = Relationship(back_populates="dataset")
    external_instances: list["ExternalInstance"] = Relationship(back_populates="dataset")
    urls: list["DatasetURL"] = Relationship(back_populates="dataset")
    tags: list["DatasetTag"] = Relationship(back_populates="dataset")
    account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    account: Optional["Account"] = Relationship(back_populates="datasets")
    status: Status = "todo"
    enabled: bool = False


class DatasetCreate(DatasetBase):
    urls: list[str] = Field(
        title="URL(s)",
        description="""
        URL(s) to the direct download of the data, if public.
        One URL per line.
        If uploading a recursive web archive dump (source type == web), 
        only the top-level URL is needed.
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
    )
    tags: list[str] = Field(
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
    def split_strings(cls, value: str | list[str]) -> list[str]:
        """Split lists of strings given as one entry per line"""
        if isinstance(value, str):
            if not value or value == "":
                return []
            value = value.splitlines()
        elif isinstance(value, list) and len(value) == 1 and "\n" in value[0]:
            value = value[0].splitlines()

        return value

    @field_validator("tags", mode="after")
    def tokenize_tags(cls, value: list[str]) -> list[str]:
        """Transform tags to lowercase alphanumeric characters, replacing anything else with -"""
        print("tokenize")
        print(value)
        res = [_tokenize(v) for v in value]
        print("after")
        print(res)
        return res


def _tokenize(v: str) -> str:
    v = v.lower()
    v = re.sub(r"[^0-9a-z\s\-_]", "", v)
    v = re.sub(r"[\s_]", "-", v)
    return v


class DatasetRead(DatasetBase, TableReadMixin):
    instances: list["DatasetInstance"]
    external_instances: list["ExternalInstance"]
    urls: list["DatasetURL"]
    tags: list["DatasetTag"]
    status: Status
    enabled: bool


class DatasetURL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="dataset.id")
    dataset: Optional[Dataset] = Relationship(back_populates="urls")
    url: str


class DatasetTag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="dataset.id")
    dataset: Optional[Dataset] = Relationship(back_populates="tags")
    tag: str


class DatasetInstanceBase(SQLModel):
    """
    A copy of a dataset
    """

    method: Optional[str] = Field(
        None,
        description="""Description of how the dataset was acquired""",
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
    )
    description: Optional[str] = Field(
        None,
        description="Any additional information about this dataset instance",
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
    )


class DatasetInstance(DatasetInstanceBase, TableMixin, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    dataset_id: Optional[int] = Field(default=None, foreign_key="dataset.id")
    dataset: Dataset = Relationship(back_populates="instances")
    account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    account: Account = Relationship(back_populates="submissions")
    torrent: Optional["TorrentFile"] = Relationship(back_populates="instance")
    enabled: bool = False

    @property
    def human_size(self) -> str:
        """Human-sized string representation of the torrent size"""
        return self.torrent.human_size

    @property
    def download_path(self) -> str:
        """Location where the torrent can be downloaded relative to site root"""
        return self.torrent.download_path

    @property
    def absolute_download_path(self) -> str:
        """Download path including the site root"""
        return urljoin(config.base_url, self.download_path)

    @property
    def file_name(self) -> str:
        return self.torrent.file_name

    @property
    def rss_description(self) -> str:
        """String to be used in the RSS description for this instance"""
        return f"Description: {self.description}\n\nMethod: {self.method}"


class DatasetInstanceRead(DatasetInstanceBase, TableReadMixin):
    """Version of datasaet instance returned when reading"""


class DatasetInstanceCreate(DatasetInstanceBase):
    """Dataset instance for creation, excludes the enabled param"""

    torrent_short_hash: str = Field(
        max_length=8, min_length=8, description="Short hash of the torrent file"
    )


class ExternalInstanceBase(SQLModel):
    """An external source for this dataset"""

    organization: str = Field(
        "", description="The name of the group or person who provides the dataset"
    )
    url: str = Field(description="Link to the external source")
    description: str = Field(
        description="Additional information about the completeness, accuracy, etc. "
        "of the external source"
    )


class ExternalInstance(ExternalInstanceBase, TableMixin, table=True):
    dataset_id: Optional[int] = Field(default=None, foreign_key="dataset.id")
    dataset: Dataset = Relationship(back_populates="external_instances")
    account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    account: Optional[Account] = Relationship(back_populates="external_submissions")
