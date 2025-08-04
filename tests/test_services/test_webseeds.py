import asyncio
import random
import string
from pathlib import Path
from typing import cast

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from torrent_models import KiB, Torrent, TorrentCreate
from torrent_models.const import EXCLUDE_FILES
from torrent_models.types.v1 import V1PieceRange
from torrent_models.types.v2 import V2PieceRange
from uvicorn.config import Config as UvicornConfig

from sciop.models import TorrentFile
from sciop.services.webseeds import validate_webseed
from sciop.testing.server import RequestHoarderMiddleware, UvicornTestServer

SIZES = [10 * KiB, 20 * KiB, 32 * KiB, 40 * KiB, 100 * KiB]


@pytest.fixture
def tmp_data_path(tmp_path: Path) -> Path:
    data_path = tmp_path / "data"
    data_path.mkdir(exist_ok=True)
    return data_path


@pytest.fixture
def rand_dir(tmp_path: Path) -> Path:
    data_path = tmp_path / "random"
    data_path.mkdir(exist_ok=True)
    return data_path


@pytest_asyncio.fixture(loop_scope="session")
async def file_server(tmp_data_path: Path, rand_dir: Path, session) -> FastAPI:
    app = FastAPI()
    app.mount("/data", StaticFiles(directory=tmp_data_path), name="data")
    app.add_middleware(RequestHoarderMiddleware)
    retries = {}

    @app.get("/404/{path}")
    async def e404(request: Request, path: str) -> None:
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/429/reasonable/{path}")
    async def e429_reasonable(request: Request, path: str) -> FileResponse:
        nonlocal retries
        if path not in retries:
            retries[path] = 0

        retries[path] += 1
        if retries[path] % 2 == 0:
            return FileResponse(tmp_data_path / path, headers=request.headers.mutablecopy())
        else:
            raise HTTPException(status_code=429)

    @app.get("/429/unreasonable/{path}")
    async def e429_unreasonable(request: Request, path: str) -> FileResponse:
        nonlocal retries
        if path not in retries:
            retries[path] = 0

        retries[path] += 1
        if retries[path] % 20 == 0:
            return FileResponse(tmp_data_path / path, headers=request.headers.mutablecopy())
        else:
            raise HTTPException(status_code=429)

    @app.get("/random/{path}")
    async def rand_response(request: Request, path: str) -> FileResponse:
        rand_path = rand_dir / path
        if not rand_path.exists():
            with open(rand_path, "wb") as f:
                f.write(random.randbytes((tmp_data_path / path).stat().st_size))

        return FileResponse(rand_path, headers=request.headers.mutablecopy())

    @app.get("/timeout/{path}")
    async def timeout(request: Request, path: str) -> FileResponse:
        await asyncio.sleep(1)
        return FileResponse(tmp_data_path / path, headers=request.headers.mutablecopy())

    @app.get("/norange/{path}")
    async def no_range(request: Request, path: str) -> Response:
        """Pretend like we don't understand range requests"""
        return Response(content=(tmp_data_path / path).read_bytes(), status_code=200, headers={})

    config = UvicornConfig(
        app=app,
        port=9998,
        workers=1,
        reload=False,
        access_log=True,
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


@pytest.fixture(
    params=[pytest.param("v1", marks=pytest.mark.v1), pytest.param("v2", marks=pytest.mark.v2)]
)
def data_torrent(request, tmp_data_path, torrentfile) -> tuple[Torrent, TorrentFile]:
    # files smaller than, same size as, and larger than piece size
    sizes = []
    for _ in range(10):
        sizes.extend(list(random.sample(SIZES, k=len(SIZES))))
    for i, size in enumerate(sizes):
        with open(tmp_data_path / string.ascii_letters[i], "wb") as f:
            f.write(random.randbytes(size))

    create = TorrentCreate(
        paths=[p for p in tmp_data_path.iterdir()], path_root=tmp_data_path, piece_length=32 * KiB
    )
    torrent = create.generate(version=request.param)
    tf: TorrentFile = torrentfile(torrent=torrent)
    return torrent, tf


@pytest.fixture(
    params=[
        pytest.param("v1", marks=pytest.mark.v1),
        pytest.param("v2", marks=pytest.mark.v2),
        pytest.param("hybrid", marks=pytest.mark.hybrid),
    ]
)
def torrent_version(request) -> str:
    return request.param


@pytest.mark.asyncio(loop_scope="session")
async def test_webseed_validation(
    tmp_data_path,
    file_server: UvicornTestServer,
    file_size,
    torrent_version,
    torrentfile,
    session,
) -> None:
    """
    We should validate correct webseeds
    """
    webseed_url = "http://localhost:9998/data/"
    create = TorrentCreate(
        paths=[p for p in tmp_data_path.iterdir()], path_root=tmp_data_path, piece_length=32 * KiB
    )
    torrent = create.generate(version=torrent_version)
    tf: TorrentFile = torrentfile(torrent=torrent)
    res = await validate_webseed(tf.infohash, webseed_url, session)

    assert res.valid

    # check that we actually requested all the urls we were supposed to.
    hoarder: RequestHoarderMiddleware = file_server.config.app.middleware_stack.app
    if torrent_version == "v1":
        expected_urls = []
        res.ranges = cast(list[V1PieceRange], res.ranges)
        for piece_range in res.ranges:
            for file_range in piece_range.ranges:
                if file_range.is_padfile:
                    continue
                expected_urls.append(webseed_url + file_range.path[0])
    else:
        res.ranges = cast(list[V2PieceRange], res.ranges)
        expected_urls = [webseed_url + r.path for r in res.ranges]

    requested = set(str(r.url) for r in hoarder.requests)
    expected = set(expected_urls)
    assert requested == expected


@pytest.mark.asyncio(loop_scope="session")
async def test_reject_invalid_data(
    data_torrent: tuple[Torrent, TorrentFile],
    rand_dir: Path,
    file_server,
    session,
    set_config,
    tmp_data_path,
):
    """
    Quit early, correctly invalidate server with incorrect data

    We test early-quitting here, so we don't do it in the rest of the tests
    """
    set_config({"services.webseed_validation.max_connections": 5})
    torrent, tf = data_torrent
    webseed_url = "http://localhost:9998/random/"

    hoarder: RequestHoarderMiddleware = file_server.config.app.middleware_stack.app
    assert set(str(r.url) for r in hoarder.requests) == set()
    res = await validate_webseed(tf.infohash, webseed_url, session)
    assert not res.valid
    assert res.error_type == "validation"

    # we should have quit after the first validation failure and not requested all the files
    # we iterate over tmp_data_path here because rand_dir only creates files on-demand,
    # so the set of files in rand dir will always, trivially, equal the set of requested urls
    all_files = set(
        [webseed_url + p.name for p in tmp_data_path.iterdir() if p.name not in EXCLUDE_FILES]
    )

    requested = set(str(r.url) for r in hoarder.requests)
    assert requested < all_files
    assert requested > set()


@pytest.mark.asyncio(loop_scope="session")
async def test_reject_404(data_torrent, file_server, session):
    """
    404's invalidate a webseed.

    This is the same mechanism for handling other non-206 responses,
    so also tests http error handling in general
    """
    torrent, tf = data_torrent
    webseed_url = "http://localhost:9998/404/"

    res = await validate_webseed(tf.infohash, webseed_url, session)
    assert not res.valid
    assert res.error_type == "http"
    assert "404" in res.message


@pytest.mark.asyncio(loop_scope="session")
async def test_reject_timeout(set_config, data_torrent, file_server, session):
    """
    Timeouts abort validation
    """
    set_config({"services.webseed_validation.get_timeout": 0.1})
    torrent, tf = data_torrent
    webseed_url = "http://localhost:9998/timeout/"

    res = await validate_webseed(tf.infohash, webseed_url, session)
    assert not res.valid
    assert res.error_type == "timeout"


@pytest.mark.asyncio(loop_scope="session")
async def test_validation_retries_success(set_config, data_torrent, file_server, session):
    """
    Retry on 429, succeed if the server eventually gives us the data
    """
    set_config(
        {
            "services.webseed_validation.retry_delay": 0.01,
            "services.webseed_validation.retries": {429: 6},
        }
    )
    torrent, tf = data_torrent
    webseed_url = "http://localhost:9998/429/reasonable/"

    res = await validate_webseed(tf.infohash, webseed_url, session)
    assert res.valid


@pytest.mark.asyncio(loop_scope="session")
async def test_validation_retries_failure(set_config, data_torrent, file_server, session):
    """
    Retry on 429, succeed if the server eventually gives us the data
    """
    set_config(
        {
            "services.webseed_validation.retry_delay": 0.01,
            "services.webseed_validation.retries": {429: 5},
        }
    )
    torrent, tf = data_torrent
    webseed_url = "http://localhost:9998/429/unreasonable/"

    res = await validate_webseed(tf.infohash, webseed_url, session)
    assert not res.valid
    assert res.error_type == "http"
    assert "429" in res.message


@pytest.mark.asyncio(loop_scope="session")
async def test_quit_early_without_range_requests(data_torrent, file_server, session):
    """
    If a server doesn't understand range requests,
    rather than downloading a potentially unbounded amount of data,
    quit early since it couldn't be used as a webseed anyway
    """
    torrent, tf = data_torrent
    webseed_url = "http://localhost:9998/norange/"

    res = await validate_webseed(tf.infohash, webseed_url, session)
    assert not res.valid
    assert res.error_type == "http"
    assert "200" in res.message
    assert "does not support HTTP range requests" in res.message
