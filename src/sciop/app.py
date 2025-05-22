from contextlib import asynccontextmanager
from typing import Generator

from fastapi import Depends, FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from sciop import jobs  # noqa: F401 - import to register
from sciop.api.deps import get_current_account
from sciop.api.main import api_router
from sciop.config import config
from sciop.config.main import _lifespan_load_config
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
from sciop.scheduler import remove_all_jobs, shutdown, start_scheduler
from sciop.services import build_docs


@asynccontextmanager
async def lifespan(app: FastAPI) -> Generator[None, None, None]:
    # loading config this must happen first
    _lifespan_load_config()

    create_tables()
    if config.env != "prod":
        build_docs(clean=False)
    start_scheduler()
    yield
    remove_all_jobs()
    shutdown()


app = FastAPI(
    title="sciop",
    openapi_url=f"{config.api_prefix}/openapi.json",
    lifespan=lifespan,
    license_info={"name": "European Union Public License - 1.2", "identifier": "EUPL-1.2"},
    docs_url="/docs/api",
    redoc_url="/docs/redoc",
    dependencies=[Depends(get_current_account)],
)

# ----------------------------------------------------------------------------------------
# Middleware
# ~~~~~~~~~~
# Order is important here!
# Middleware run in "outside-in-then-return" order:
# before the endpoint method - starting from the most recently added (later lines),
# after the endpoint method - back up in reverse order (earlier lines)
#
# When adding new middleware, you likely want to add it to the *top* (inside) of the stack,
# but mind any comments that describe the position of a middleware
# -----------------------------------------------------------------------------------------

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(ContentSizeLimitMiddleware, max_content_size=config.upload_limit)
app.middleware("http")(security_headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.server.base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging wraps the other middlewares (except gzip),
# because it also is responsible for timing responses
app.add_middleware(LoggingMiddleware, logger=init_logger("requests"))

# GZip should be the very outer middleware, since the response is completed,
# just needs to be compressed. and coming earlier requires other middlewares to decompress.
app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=5)


app.include_router(api_router)
app.include_router(frontend_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/torrents", StaticFiles(directory=config.paths.torrents), name="torrents")
DOCS_DIR.mkdir(exist_ok=True)
app.mount("/docs", StaticFiles(directory=DOCS_DIR, html=True), name="docs")
add_pagination(app)

app.add_exception_handler(429, rate_limit_handler)
app.add_exception_handler(StarletteHTTPException, http_handler)
