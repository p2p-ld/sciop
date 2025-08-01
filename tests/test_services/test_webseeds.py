import random
import string
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from torrent_models import KiB, TorrentCreate
from uvicorn.config import Config as UvicornConfig

from sciop.models import TorrentFile
from sciop.services.webseeds import validate_webseed
from sciop.testing.server import UvicornTestServer

SIZES = [10 * KiB, 20 * KiB, 32 * KiB, 40 * KiB, 100 * KiB]


@pytest.fixture
def tmp_data_path(tmp_path: Path) -> Path:
    data_path = tmp_path / "data"
    data_path.mkdir(exist_ok=True)
    return data_path


@pytest_asyncio.fixture(loop_scope="session")
async def file_server(tmp_data_path: Path) -> FastAPI:
    app = FastAPI()
    app.mount("/data", StaticFiles(directory=tmp_data_path), name="data")

    config = UvicornConfig(
        app=app,
        port=9998,
        workers=1,
        reload=False,
    )
    server = UvicornTestServer(config=config)
    await server.up()
    yield server
    await server.down()


@pytest.fixture(params=SIZES)
def file_size(request, tmp_data_path) -> int:
    size = request.param
    for name in string.ascii_letters[0:10]:
        with open(tmp_data_path / name, "wb") as f:
            f.write(random.randbytes(size))
    return size


@pytest.fixture(params=["v1", "v2", "hybrid"])
def torrent_version(request) -> str:
    return request.param


@pytest.mark.skip("run manually first to not potentially have ci freeze forever")
async def test_webseed_validation(
    tmp_data_path, file_server, file_size, torrent_version, torrentfile
) -> None:
    """
    We should validate correct webseeds
    """
    create = TorrentCreate(
        paths=[p for p in tmp_data_path.iterdir()], path_root=tmp_data_path, piece_length=32 * KiB
    )
    torrent = create.generate(version=torrent_version)
    tf: TorrentFile = torrentfile(torrent=torrent)

    validate_webseed(tf.infohash, "http://localhost:9998/data/")
    raise NotImplementedError("Finish this test")


@pytest.mark.skip
async def test_reject_invalid_data():
    """
    Quit early, correctly invalidate server with incorrect data
    """


@pytest.mark.skip
async def test_reject_404():
    """
    Test that http errors like 404 quit early, invalidate webseed
    """


@pytest.mark.skip
async def test_reject_timeout():
    """
    Timeouts abort validation
    """


@pytest.mark.skip
async def test_validation_retries():
    """
    Retry on 429
    """


@pytest.mark.skip
def test_quit_early_without_range_requests():
    """
    If a server doesn't understand range requests,
    rather than downloading a potentially unbounded amount of data,
    quit early since it couldn't be used as a webseed anyway
    """
    raise NotImplementedError()
