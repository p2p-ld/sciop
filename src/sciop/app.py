from contextlib import asynccontextmanager
from typing import Generator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from sciop.api.main import api_router
from sciop.config import config
from sciop.const import DOCS_DIR, STATIC_DIR
from sciop.db import create_tables
from sciop.exceptions import http_handler, rate_limit_handler
from sciop.frontend.main import frontend_router
from sciop.logging import init_logger
from sciop.middleware import (
    ContentSizeLimitMiddleware,
    LoggingMiddleware,
    limiter,
    security_headers,
)
from sciop.scheduler import start_scheduler
from sciop.services import build_docs
from sciop.udp import create_udp_tracker_client

# def custom_generate_unique_id(route: APIRoute) -> str:
#     return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(app: FastAPI) -> Generator[None, None, None]:
    create_tables()
    build_docs()
    start_scheduler()
    url = "udp://open.demonii.com:1337"
    tracker = await create_udp_tracker_client(
        url, torrents={"a2a9daf05d6e276d47b48da9debc845a0d47a5b9": None}
    )
    await tracker.initiate_connection()
    await tracker.request_scrape()
    yield


app = FastAPI(
    title="sciop",
    openapi_url=f"{config.api_prefix}/openapi.json",
    # generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
    license_info={"name": "European Union Public License - 1.2", "identifier": "EUPL-1.2"},
    docs_url="/docs/api",
    redoc_url="/docs/redoc",
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(ContentSizeLimitMiddleware, max_content_size=config.upload_limit)
app.middleware("http")(security_headers)
app.add_middleware(LoggingMiddleware, logger=init_logger("requests"))
app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=5)

# Set all CORS enabled origins
if config.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app.include_router(api_router)
app.include_router(frontend_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/torrents", StaticFiles(directory=config.torrent_dir), name="torrents")
DOCS_DIR.mkdir(exist_ok=True)
app.mount("/docs", StaticFiles(directory=DOCS_DIR, html=True), name="docs")
add_pagination(app)

app.add_exception_handler(429, rate_limit_handler)
app.add_exception_handler(StarletteHTTPException, http_handler)


def main() -> None:
    uvicorn.run(
        "sciop.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        reload_includes=["*.py", "*.md", "*.yml"],
        lifespan="on",
        access_log=False,
    )
