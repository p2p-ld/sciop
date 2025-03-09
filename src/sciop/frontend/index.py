from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

import sciop
from sciop.api.deps import CurrentAccount, RequireCurrentAccount
from sciop.const import STATIC_DIR
from sciop.frontend.templates import templates
from sciop.models import DatasetCreate
from sciop.scheduler import interval, print_job, remove_all_jobs

index_router = APIRouter()


@index_router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # temp place for a printer
    # add_job(
    #     print_job,
    #     msg="EVERY FIVE SECONDS ANOTHER DATASET DISAPPEARS, BUT WITH YOUR HELP",
    #     seconds=5,
    #     num=10,
    # )
    # add_job(print_job, 'interval', {}, "Just an arg, love, just an arg!", seconds = 10)
    interval(print_job, "Just a little arg, why, just a wee little arg!", 765, seconds=10)
    remove_all_jobs()
    try:
        short_hash = sciop.__version__.split("+")[1]
    except IndexError:
        short_hash = ""
    return templates.TemplateResponse(
        request,
        "pages/index.html",
        {
            "version": sciop.__version__,
            "short_hash": short_hash,
        },
    )


@index_router.get("/feeds", response_class=HTMLResponse)
async def feeds(request: Request):
    return templates.TemplateResponse(request, "pages/feeds.html")


@index_router.get("/login", response_class=HTMLResponse)
async def login(request: Request, current_account: CurrentAccount):
    if current_account:
        return RedirectResponse("/self")
    return templates.TemplateResponse(request, "pages/login.html")


@index_router.get("/request", response_class=HTMLResponse)
async def request(request: Request, account: RequireCurrentAccount):
    return templates.TemplateResponse(request, "pages/request.html", {"model": DatasetCreate})


@index_router.get("/upload", response_class=HTMLResponse)
async def upload(request: Request, account: CurrentAccount):
    if account is None:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(request, "pages/upload.html")


@index_router.get("/favicon.ico", response_class=FileResponse, include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / "img" / "favicon.ico")
