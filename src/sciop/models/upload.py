from typing import Optional
from urllib.parse import urljoin

from sqlmodel import Field, Relationship, SQLModel

from sciop.config import config
from sciop.models import Account, AuditLog, Dataset, DatasetPart, TorrentFile
from sciop.models.mixin import TableMixin, TableReadMixin
from sciop.types import EscapedStr, IDField, InputType


class UploadBase(SQLModel):
    """
    A copy of a dataset
    """

    method: Optional[EscapedStr] = Field(
        None,
        description="""Description of how the dataset was acquired""",
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
        max_length=2048,
    )
    description: Optional[EscapedStr] = Field(
        None,
        description="Any additional information about this dataset upload",
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
        max_length=4096,
    )


class Upload(UploadBase, TableMixin, table=True):
    upload_id: IDField = Field(default=None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="dataset.dataset_id")
    dataset: Dataset = Relationship(back_populates="uploads")
    dataset_part_id: Optional[int] = Field(default=None, foreign_key="dataset_part.dataset_part_id")
    dataset_part: DatasetPart = Relationship(back_populates="uploads")
    account_id: Optional[int] = Field(default=None, foreign_key="account.account_id")
    account: Account = Relationship(back_populates="submissions")
    torrent: Optional["TorrentFile"] = Relationship(
        back_populates="upload", sa_relationship_kwargs={"lazy": "selectin"}
    )
    enabled: bool = False
    audit_log_target: list["AuditLog"] = Relationship(back_populates="target_upload")

    @property
    def human_size(self) -> str:
        """Human-sized string representation of the torrent size"""
        return self.torrent.human_size

    @property
    def human_torrent_size(self) -> str:
        """Human-sized string representation of the size of the torrent itself"""
        return self.torrent.human_torrent_size

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
    def short_hash(self) -> str:
        return self.torrent.short_hash

    @property
    def rss_description(self) -> str:
        """String to be used in the RSS description for this upload"""
        return f"Description: {self.description}\n\nMethod: {self.method}"


class UploadRead(UploadBase, TableReadMixin):
    """Version of datasaet upload returned when reading"""

    torrent: Optional["TorrentFile"] = None


class UploadCreate(UploadBase):
    """Dataset upload for creation, excludes the enabled param"""

    torrent_short_hash: str = Field(
        max_length=8, min_length=8, description="Short hash of the torrent file"
    )
