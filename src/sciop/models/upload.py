from typing import Optional
from urllib.parse import urljoin

from sqlalchemy import event
from sqlalchemy.orm.attributes import AttributeEventToken
from sqlmodel import Field, Relationship, SQLModel

from sciop.config import config
from sciop.models import Account, AuditLog, Dataset, DatasetPart, TorrentFile
from sciop.models.dataset import UploadDatasetPartLink
from sciop.models.mixin import ModerableMixin, TableMixin, TableReadMixin
from sciop.types import EscapedStr, IDField, InputType, SlugStr


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


class Upload(UploadBase, TableMixin, ModerableMixin, table=True):
    __tablename__ = "uploads"

    upload_id: IDField = Field(default=None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="datasets.dataset_id")
    dataset: Dataset = Relationship(back_populates="uploads")
    dataset_parts: list[DatasetPart] = Relationship(
        back_populates="uploads", link_model=UploadDatasetPartLink
    )
    account_id: Optional[int] = Field(default=None, foreign_key="accounts.account_id")
    account: Account = Relationship(back_populates="submissions")
    torrent: Optional["TorrentFile"] = Relationship(
        back_populates="upload", sa_relationship_kwargs={"lazy": "selectin"}
    )

    audit_log_target: list["AuditLog"] = Relationship(back_populates="target_upload")
    seeders: Optional[int] = None
    leechers: Optional[int] = None

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
    def infohash(self) -> str:
        return self.torrent.infohash

    @property
    def rss_description(self) -> str:
        """
        String to be used in the RSS description for this upload

        Todo: dump all model details here programmatically instead of hardcoded like this
        """
        return f"""
            <p>
            <strong>Dataset:</strong> 
              <a href="{config.base_url}/datasets/{self.dataset.slug}">
                {config.base_url}/datasets/{self.dataset.slug}
              </a>
            </p>
            <p>
            <strong>Upload:</strong> 
              <a href="{config.base_url}/uploads/{self.infohash}">
              {config.base_url}/uploads/{self.infohash}
              </a>
            </p>
            <p>
            <strong>Description:</strong> {self.description}
            </p>
            <p>
            <strong>Method:</strong> {self.method}
            </p>
        """


@event.listens_for(Upload.is_removed, "set")
def _upload_remove_torrent(
    target: Upload, value: bool, oldvalue: bool, initiator: AttributeEventToken
) -> None:
    """Remove an associated torrent when the"""
    if value and target.torrent:
        from sciop.db import get_session

        with next(get_session()) as session:
            torrent = session.merge(target.torrent)
            session.delete(torrent)
            session.commit()


class UploadRead(UploadBase, TableReadMixin):
    """Version of datasaet upload returned when reading"""

    torrent: Optional["TorrentFile"] = None


class UploadCreate(UploadBase):
    """Dataset upload for creation, excludes the is_approved param"""

    torrent_infohash: str = Field(
        min_length=40, max_length=64, description="Infohash of the torrent file, v1 or v2"
    )
    part_slugs: Optional[list[SlugStr]] = Field(
        default=None,
        title="Dataset Parts",
        description="Parts of a dataset that this upload corresponds to",
    )
