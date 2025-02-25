from sciop.models.account import (
    Account,
    AccountCreate,
    AccountRead,
    AccountScopeLink,
    Scope,
    Scopes,
    Token,
    TokenPayload,
)
from sciop.models.api import SuccessResponse
from sciop.models.dataset import (
    Dataset,
    DatasetCreate,
    DatasetPart,
    DatasetPartCreate,
    DatasetPartRead,
    DatasetPath,
    DatasetRead,
    DatasetURL,
    ExternalIdentifier,
    ExternalIdentifierCreate,
    ExternalSource,
)
from sciop.models.moderation import AuditLog, AuditLogRead, ModerationAction
from sciop.models.rss import TorrentFeed, TorrentItem
from sciop.models.tag import DatasetTagLink, Tag, TagSummary
from sciop.models.torrent import (
    FileInTorrent,
    FileInTorrentCreate,
    Torrent,
    TorrentFile,
    TorrentFileCreate,
    TorrentFileRead,
    TrackerInTorrent,
)
from sciop.models.upload import Upload, UploadCreate, UploadRead

Dataset.model_rebuild()
DatasetRead.model_rebuild()
DatasetPart.model_rebuild()
DatasetPartRead.model_rebuild()

__all__ = [
    "Account",
    "AccountCreate",
    "AccountRead",
    "AccountScopeLink",
    "AuditLog",
    "AuditLogRead",
    "Dataset",
    "DatasetCreate",
    "DatasetPart",
    "DatasetPartCreate",
    "DatasetPartRead",
    "DatasetPath",
    "DatasetRead",
    "DatasetURL",
    "DatasetTagLink",
    "ExternalIdentifier",
    "ExternalIdentifierCreate",
    "ExternalSource",
    "FileInTorrent",
    "FileInTorrentCreate",
    "ModerationAction",
    "Scope",
    "Scopes",
    "SuccessResponse",
    "Tag",
    "TagSummary",
    "Token",
    "TokenPayload",
    "Torrent",
    "TorrentFeed",
    "TorrentFile",
    "TorrentFileCreate",
    "TorrentFileRead",
    "TorrentItem",
    "TrackerInTorrent",
    "Upload",
    "UploadCreate",
    "UploadRead",
]
