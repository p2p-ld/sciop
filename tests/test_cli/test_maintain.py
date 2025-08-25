import random
from datetime import UTC, datetime, timedelta

from click.testing import CliRunner
from sqlmodel import select
from torrent_models import TorrentCreate

from sciop.cli.maintain import validate_queued
from sciop.models import Webseed


def test_validate_queued(session, torrentfile, httpx_mock, tmp_path):
    paths = [tmp_path / "a", tmp_path / "b", tmp_path / "c"]
    torrents = []
    for path in paths:
        path.write_bytes(random.randbytes(16 * (2**10)))
        tcreate = TorrentCreate(
            paths=[path],
            path_root=tmp_path,
            piece_length=16 * (2**10),
            trackers=["https://example.com"],
        )
        torrents.append(tcreate.generate("hybrid"))

    for path in paths:
        httpx_mock.add_response(
            url=f"https://example.com/{path.name}", content=path.read_bytes(), status_code=206
        )

    torrents = [torrentfile(torrent=t) for t in torrents]
    for t in torrents:
        t.webseeds = [
            Webseed(
                status="queued",
                url="https://example.com",
                created_at=datetime.now(UTC) - timedelta(days=1),
            )
        ]
        session.add(t)
    session.commit()

    runner = CliRunner()
    result = runner.invoke(validate_queued)
    assert result.exit_code == 0

    # all the urls should have been hit - the fixture should error if any of them aren't hit,
    # but want to keep it explicit
    requests = httpx_mock.get_requests()
    assert len(requests) == 3

    # all the webseeds should have been validated
    webseeds = session.exec(select(Webseed)).all()
    assert len(webseeds) == 3
    for ws in webseeds:
        assert ws.status == "validated"
