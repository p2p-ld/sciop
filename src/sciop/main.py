from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.orm import scoped_session
from starlette.middleware.cors import CORSMiddleware

from sciop.api.main import api_router
from sciop.config import config
from sciop.const import STATIC_DIR
from sciop.db import create_tables
from sciop.frontend.main import frontend_router
from sciop.limiter import sciop_limiter

# def custom_generate_unique_id(route: APIRoute) -> str:
#     return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="sciop",
    openapi_url=f"{config.api_prefix}/openapi.json",
    # generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
    license_info={
        "name": "European Union Public License - 1.2",
        "identifier": "EUPL-1.2"
    },
    docs_url="/docs/api",
    redoc_url="/docs/redoc"
)

app.state.limiter = sciop_limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(429, _rate_limit_exceeded_handler)

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
add_pagination(app)

# app.add_middleware(
#     ContentSizeLimitMiddleware,
#     max_content_size = config.upload_limit
# )


def main():
    uvicorn.run("sciop.main:app", host=config.host, port=config.port, reload=config.reload)
