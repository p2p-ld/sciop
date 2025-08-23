"""
Update site stats
"""

from pprint import pformat
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import func
from sqlmodel import Session, select, text

from sciop.logging import init_logger

if TYPE_CHECKING:
    from sciop.models import (
        SiteStats,
    )


logger = init_logger("sciop.stats")


class PeerStats(TypedDict):
    """Counts that can be grabbed efficiently together in get_peer_stats"""

    n_seeders: int
    n_downloaders: int
    total_capacity: int
    total_size: int


def update_site_stats() -> None:
    """
    Update the site stats, a summary of the current number of datasets indexed,
    their peers (if present), and size.
    """
    global logger
    from sciop.db import get_session

    with get_session() as session:
        stats = get_site_stats(session)
        session.add(stats)
        session.commit()

    logger.info("Updated site stats: %s", pformat(stats.model_dump()))


def get_site_stats(session: Session) -> "SiteStats":
    global logger
    from sciop.models import SiteStats

    peer_stats = get_peer_stats(session)
    logger.debug(f"Got peer stats: {peer_stats}")

    stats = SiteStats(
        n_datasets=get_n_datasets(session),
        n_uploads=get_n_uploads(session),
        n_files=get_n_files(session),
        **peer_stats,
    )
    return stats


def get_peer_stats(session: Session) -> PeerStats:
    # in the inner query, get the n leechers/seeders per torrent
    from sciop.models import TorrentFile, TorrentTrackerLink, Upload, Webseed

    webseed_subquery = (
        select(func.count(Webseed.webseed_id).label("webseeds"))
        .where(
            Webseed.status.in_(("in_original", "validated")),
            TorrentFile.torrent_file_id == Webseed.torrent_id,
        )
        .scalar_subquery()
    )

    peer_count_subquery = (
        select(
            func.max(TorrentTrackerLink.leechers).label("leechers"),
            func.max(TorrentTrackerLink.seeders).label("seeders"),
            webseed_subquery.label("webseeds"),
            TorrentFile.total_size.label("total_size"),
        )
        .join(TorrentTrackerLink.torrent)
        .join(TorrentFile.upload)
        .group_by(TorrentFile.torrent_file_id)
        .where(Upload.is_visible == True)
        .subquery()
    )

    # then take the sum of all leechers, seeders, and multiply by size to get capacity
    peer_count_stmt = select(
        func.sum(text("leechers")).label("n_downloaders"),
        func.sum(text("seeders + webseeds")).label("n_seeders"),
        func.sum(text("(seeders + webseeds) * total_size")).label("total_capacity"),
        func.sum(text("total_size")).label("total_size"),
    ).select_from(peer_count_subquery)

    peer_counts = session.exec(peer_count_stmt).first()
    return PeerStats(peer_counts._asdict())


def get_n_datasets(session: Session) -> int:
    from sciop.models import Dataset

    dataset_count_stmt = select(func.count(Dataset.dataset_id).label("n_datasets")).where(
        Dataset.is_visible == True
    )
    return session.exec(dataset_count_stmt).first()


def get_n_uploads(session: Session) -> int:
    from sciop.models import Upload

    upload_count_stmt = select(func.count(Upload.upload_id).label("n_uploads")).where(
        Upload.is_visible == True
    )
    return session.exec(upload_count_stmt).first()


def get_n_files(session: Session) -> int:
    from sciop.models import FileInTorrent, TorrentFile, Upload

    n_files_stmt = (
        select(func.count(FileInTorrent.file_in_torrent_id).label("n_files"))
        .join(FileInTorrent.torrent)
        .join(TorrentFile.upload)
        .where(Upload.is_visible == True)
    )
    return session.exec(n_files_stmt).first()
