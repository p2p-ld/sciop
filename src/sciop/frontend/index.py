from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sciop.const import TEMPLATE_DIR
from sciop.config import config
from sciop.api.deps import CurrentAccount

index_router = APIRouter()



templates = Jinja2Templates(
    directory=TEMPLATE_DIR
)

@index_router.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse('pages/index.html', {"request": request, "config": config})

@index_router.get('/login', response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse('pages/login.html', {"request": request, "config": config})

@index_router.get("/account", response_class=HTMLResponse)
async def account(request: Request, account: CurrentAccount):
    if account is None:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse('pages/account.html', {"request": request, "config": config, "account": account})


