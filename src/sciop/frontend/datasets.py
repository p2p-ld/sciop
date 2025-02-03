from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sciop import crud
from sciop.api.deps import CurrentAccount, SessionDep
from sciop.config import config
from sciop.const import TEMPLATE_DIR
from sciop.models import DatasetCreate

datasets_router = APIRouter(prefix="/datasets")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


@datasets_router.get("/{dataset_slug}", response_class=HTMLResponse)
async def dataset_show(
    dataset_slug: str, account: CurrentAccount, session: SessionDep, request: Request
):
    dataset = crud.get_dataset(session=session, dataset_slug=dataset_slug)
    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"No such dataset {dataset_slug} exists",
        )
    return templates.TemplateResponse(
        "pages/dataset.html",
        {"request": request, "config": config, "current_account": account, "dataset": dataset},
    )


@datasets_router.get("/{dataset_slug}/upload/start", response_class=HTMLResponse)
async def dataset_upload_start(
    dataset_slug: str, account: CurrentAccount, session: SessionDep, request: Request
):
    dataset = crud.get_dataset(session=session, dataset_slug=dataset_slug)
    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"No such dataset {dataset_slug} exists",
        )

    print(dataset.model_dump().items())
    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"No such dataset {dataset_slug} exists",
        )
    return templates.TemplateResponse(
        "partials/upload_start.html",
        {"request": request, "config": config, "current_account": account, "dataset": dataset},
    )
