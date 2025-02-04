from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sciop.api.deps import CurrentAccount, SessionDep
from sciop.config import config
from sciop.const import TEMPLATE_DIR
from sciop.models import DatasetCreate
from sciop import crud

index_router = APIRouter()


templates = Jinja2Templates(directory=TEMPLATE_DIR)


@index_router.get("/", response_class=HTMLResponse)
async def index(request: Request, account: CurrentAccount, session: SessionDep):
    datasets = crud.get_approved_datasets(session=session)
    return templates.TemplateResponse(
        "pages/index.html",
        {"request": request, "config": config, "current_account": account, "datasets": datasets},
    )


@index_router.get("/login", response_class=HTMLResponse)
async def login(request: Request, account: CurrentAccount):
    return templates.TemplateResponse(
        "pages/login.html", {"request": request, "config": config, "current_account": account}
    )


@index_router.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, account: CurrentAccount):
    if account is None:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(
        "pages/profile.html", {"request": request, "config": config, "current_account": account}
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
