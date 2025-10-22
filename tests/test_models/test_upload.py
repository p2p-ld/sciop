from textwrap import dedent

import pytest
from sqlmodel import select

from sciop.models import Upload


@pytest.fixture()
def props_uploads(upload, dataset, torrentfile, session) -> tuple[Upload, ...]:
    """Uploads with values set to test hybrid properties"""
    seeds = [None, 1, 5]
    sizes = [2**10, 2**20, 2**30]
    size_names = ["1kb", "1mb", "1gb"]

    ds = dataset()
    uploads = []
    for seed, size, size_name in zip(seeds, sizes, size_names):
        tf = torrentfile(file_name=f"{seed}_{size_name}.torrent")
        if seed is not None:
            tf.tracker_links[0].seeders = seed
            tf.tracker_links[0].leechers = seed
        tf.total_size = size
        session.add(tf)
        session.commit()

        ul = upload(dataset_=ds, torrentfile_=tf)
        uploads.append(ul)
    return tuple(uploads)


def test_prefix_torrent_on_removal(upload, session):
    """
    Marking an upload as removed prefixes the infohashes in its torrent file
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
    assert "REM" in ul.torrent.v1_infohash
    assert "REM" in ul.torrent.v2_infohash
    assert torrent_file.exists()


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


def test_upload_hybrid_props_seeders(session, props_uploads):
    """Seeders should behave correctly in queries and in ORM"""
    uls = session.exec(select(Upload).where(Upload.seeders > 1)).all()
    assert len(uls) == 1
    assert uls[0].seeders == 5

    uls = session.exec(select(Upload).where(Upload.seeders <= 5)).all()
    assert len(uls) == 2
    assert sorted([ul.seeders for ul in uls]) == [1, 5]

    uls = session.exec(select(Upload).where(Upload.seeders == None)).all()  # noqa: E711
    assert len(uls) == 1
    assert uls[0].seeders is None


def test_upload_hybrid_props_leechers(session, props_uploads):
    uls = session.exec(select(Upload).where(Upload.leechers > 1)).all()
    assert len(uls) == 1
    assert uls[0].leechers == 5

    uls = session.exec(select(Upload).where(Upload.leechers <= 5)).all()
    assert len(uls) == 2
    assert sorted([ul.leechers for ul in uls]) == [1, 5]

    uls = session.exec(select(Upload).where(Upload.leechers == None)).all()  # noqa: E711
    assert len(uls) == 1
    assert uls[0].leechers is None


def test_upload_hybrid_props_size(session, props_uploads):
    uls = session.exec(select(Upload).where(Upload.size > 2**20)).all()
    assert len(uls) == 1
    assert uls[0].size == 2**30

    uls = session.exec(select(Upload).where(Upload.size <= 2**20)).all()
    assert len(uls) == 2
    assert sorted([ul.size for ul in uls]) == [2**10, 2**20]
