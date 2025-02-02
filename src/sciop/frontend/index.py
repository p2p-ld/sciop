from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from sciop.const import TEMPLATE_DIR

index_router = APIRouter()



templates = Jinja2Templates(
    directory=TEMPLATE_DIR
)

@index_router.get('/', response_class=HTMLResponse)
async def index(request: Request):
    print('index')
    return templates.TemplateResponse('pages/index.html', {"request": request})
