from sqlmodel import select

from sciop.models import TorrentFile, Upload


def test_remove_torrent_on_removal(upload, session):
    """
    Marking an upload as removed deletes its torrent file
    """
    ul: Upload = upload()
    torrent_id = ul.torrent.torrent_file_id
    torrent_file = ul.torrent.filesystem_path
    assert torrent_file.exists()
    assert not ul.is_removed
    ul.is_removed = True
    session.add(ul)
    session.commit()
    session.refresh(ul)
    assert ul.is_removed
    assert (
        session.exec(select(TorrentFile).where(TorrentFile.torrent_file_id == torrent_id)).first()
        is None
    )
    assert not torrent_file.exists()
