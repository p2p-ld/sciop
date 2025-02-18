from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

import sciop
from sciop.api.deps import CurrentAccount
from sciop.config import config
from sciop.const import STATIC_DIR
from sciop.frontend.templates import templates
from sciop.models import DatasetCreate

index_router = APIRouter()


@index_router.get("/", response_class=HTMLResponse)
async def index(request: Request, account: CurrentAccount):
    try:
        short_hash = sciop.__version__.split("+")[1]
    except IndexError:
        short_hash = ""
    return templates.TemplateResponse(
        request,
        "pages/index.html",
        {
            "request": request,
            "config": config,
            "current_account": account,
            "version": sciop.__version__,
            "short_hash": short_hash,
        },
    )


@index_router.get("/login", response_class=HTMLResponse)
async def login(request: Request, account: CurrentAccount):
    return templates.TemplateResponse(
        "pages/login.html", {"request": request, "config": config, "current_account": account}
    )


@index_router.get("/request", response_class=HTMLResponse)
async def request(request: Request, account: CurrentAccount):
    return templates.TemplateResponse(
        "pages/request.html",
        {"request": request, "config": config, "current_account": account, "model": DatasetCreate},
    )


@index_router.get("/upload", response_class=HTMLResponse)
async def upload(request: Request, account: CurrentAccount):
    if account is None:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(
        "pages/upload.html", {"request": request, "config": config, "current_account": account}
    )


@index_router.get("/favicon.ico", response_class=FileResponse, include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / "img" / "favicon.ico")
