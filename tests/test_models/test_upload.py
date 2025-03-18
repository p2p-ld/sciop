from textwrap import dedent

from sqlmodel import select

from sciop.models import TorrentFile, Upload


def test_remove_torrent_on_removal(upload, session):
    """
    Marking an upload as removed deletes its torrent file
    """
    ul: Upload = upload(session=session)
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


def test_upload_description_html_rendering(upload, session):
    """
    Dataset descriptions are rendered to html
    """
    description = dedent(
        """## I am a heading
        """
    )
    ul: Upload = upload(description=description)
    assert ul.description == description
    assert ul.description_html == '<div class="markdown"><h2>I am a heading</h2></div>'
    new_description = "A new description"
    ul.description = new_description
    session.add(ul)
    session.commit()
    session.refresh(ul)
    assert ul.description == new_description
    assert ul.description_html == '<div class="markdown"><p>A new description</p></div>'


def test_upload_method_html_rendering(upload, session):
    """
    Dataset descriptions are rendered to html
    """
    method = dedent(
        """**This is important**
        """
    )
    ul: Upload = upload(method=method)
    assert ul.method == method
    assert ul.method_html == '<div class="markdown"><p><strong>This is important</strong></p></div>'
    new_method = "A different method"
    ul.method = new_method
    session.add(ul)
    session.commit()
    session.refresh(ul)
    assert ul.method == new_method
    assert ul.method_html == '<div class="markdown"><p>A different method</p></div>'


def test_upload_without_torrent_visibility(upload, session):
    """
    An upload that miraculously loses its torrent should not be visible
    """
    ul = upload(is_approved=True)
    assert ul.torrent is not None
    assert ul.is_visible
    session.delete(ul.torrent)
    session.commit()
    session.refresh(ul)
    assert ul.is_approved
    assert not ul.is_removed
    assert ul.torrent is None
    assert not ul.is_visible

    # and the hybrid property
    visible_uls = session.exec(select(Upload).where(Upload.is_visible == True)).all()
    assert len(visible_uls) == 0
