# this must happen before tables start to be defined,
# so it must happen at a module level,
# it must be this module,
# and it must happen before the imports
# so as a result...
# ruff: noqa: E402

from sciop.models.base import SQLModel

SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s_%(column_0_N_name)s",
}

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
from sciop.models.api import (
    RaggedSearchPage,
    RaggedSearchParams,
    SearchPage,
    SearchParams,
    SuccessResponse,
)
from sciop.models.claim import ClaimStatus, DatasetClaim, DatasetClaimCreate, DatasetClaimRead
from sciop.models.counter import HitCount
from sciop.models.dataset import (
    Dataset,
    DatasetCreate,
    DatasetPart,
    DatasetPartCreate,
    DatasetPartRead,
    DatasetPath,
    DatasetRead,
    DatasetUpdate,
    DatasetURL,
    ExternalIdentifier,
    ExternalIdentifierCreate,
    ExternalSource,
)
from sciop.models.magnet import MagnetLink
from sciop.models.mixins import EditableMixin
from sciop.models.moderation import AuditLog, AuditLogRead, ModerationAction
from sciop.models.mystery import _Friedolin
from sciop.models.rss import TorrentFeed, TorrentItem
from sciop.models.stats import SiteStats, SiteStatsRead
from sciop.models.tag import DatasetTagLink, Tag, TagSummary
from sciop.models.torrent import (
    FileInTorrent,
    FileInTorrentCreate,
    FileInTorrentRead,
    Torrent,
    TorrentFile,
    TorrentFileCreate,
    TorrentFileRead,
)
from sciop.models.tracker import TorrentTrackerLink, Tracker, TrackerCreate
from sciop.models.upload import Upload, UploadCreate, UploadRead, UploadUpdate

Account.model_rebuild()
Dataset.model_rebuild()
DatasetRead.model_rebuild()
DatasetPart.model_rebuild()
DatasetPartRead.model_rebuild()
Scope.model_rebuild()
TorrentFile.model_rebuild()
EditableMixin.rebuild_history_models(namespace=locals())

__all__ = [
    "Account",
    "AccountCreate",
    "AccountRead",
    "AccountScopeLink",
    "AuditLog",
    "AuditLogRead",
    "ClaimStatus",
    "Dataset",
    "DatasetClaim",
    "DatasetClaimCreate",
    "DatasetClaimRead",
    "DatasetCreate",
    "DatasetPart",
    "DatasetPartCreate",
    "DatasetPartRead",
    "DatasetPath",
    "DatasetRead",
    "DatasetUpdate",
    "DatasetURL",
    "DatasetTagLink",
    "ExternalIdentifier",
    "ExternalIdentifierCreate",
    "ExternalSource",
    "FileInTorrent",
    "FileInTorrentCreate",
    "FileInTorrentRead",
    "HitCount",
    "MagnetLink",
    "ModerationAction",
    "RaggedSearchPage",
    "RaggedSearchParams",
    "Scope",
    "Scopes",
    "SearchPage",
    "SearchParams",
    "SiteStats",
    "SiteStatsRead",
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
    "TorrentTrackerLink",
    "Tracker",
    "TrackerCreate",
    "Upload",
    "UploadCreate",
    "UploadRead",
    "UploadUpdate",
    "_Friedolin",
]
