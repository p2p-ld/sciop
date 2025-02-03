from typing import TYPE_CHECKING, Optional
from sqlmodel import SQLModel, Relationship, Field
from sciop.models.mixin import TableMixin

if TYPE_CHECKING:
    from sciop.models.dataset import Account, DatasetInstance


class TorrentFileBase(SQLModel):
    file_name: str

    pass


class TorrentFile(TorrentFileBase, TableMixin, table=True):
    account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    account: "Account" = Relationship(back_populates="torrents")
    instance_id: Optional[int] = Field(default=None, foreign_key="datasetinstance.id")
    instance: Optional["DatasetInstance"] = Relationship(back_populates="torrent")


class TorrentFileCreate(TorrentFileBase):

    @classmethod
    def from_stream(cls):
        raise NotImplementedError("do this")
