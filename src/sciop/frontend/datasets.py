from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop import crud
from sciop.api.deps import CurrentAccount, RequireDataset, RequireUploader, SessionDep
from sciop.api.routes.upload import upload_torrent
from sciop.config import config
from sciop.frontend.templates import jinja, templates
from sciop.models import Dataset, DatasetRead, UploadCreate

datasets_router = APIRouter(prefix="/datasets")


@datasets_router.get("/", response_class=HTMLResponse)
async def datasets(request: Request, account: CurrentAccount, session: SessionDep):
    datasets = crud.get_approved_datasets(session=session)
    return templates.TemplateResponse(
        "pages/datasets.html",
        {"request": request, "config": config, "current_account": account, "datasets": datasets},
    )


@datasets_router.get("/search")
@jinja.hx("partials/datasets.html")
async def datasets_search(query: str = None, session: SessionDep = None) -> Page[DatasetRead]:
    if not query or len(query) < 3:
        stmt = select(Dataset).where(Dataset.enabled == True).order_by(Dataset.created_at)
    else:
        stmt = (
            select(Dataset)
            .where(Dataset.enabled == True)
            .filter(Dataset.id.in_(Dataset.search_statement(query)))
        )
    return paginate(conn=session, query=stmt)


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


@datasets_router.get("/{dataset_slug}/partial", response_class=HTMLResponse)
async def dataset_partial(request: Request, dataset: RequireDataset):
    return templates.TemplateResponse(
        "partials/dataset.html", {"dataset": dataset, "request": request}
    )


@datasets_router.get("/{dataset_slug}/uploads", response_class=HTMLResponse)
async def dataset_uploads(
    dataset_slug: str,
    account: CurrentAccount,
    dataset: RequireDataset,
    session: SessionDep,
    request: Request,
):
    uploads = crud.get_uploads(dataset=dataset, session=session)
    return templates.TemplateResponse(
        "partials/dataset-uploads.html",
        {"request": request, "config": config, "uploads": uploads, "dataset": dataset},
    )


@datasets_router.get("/{dataset_slug}/upload/start", response_class=HTMLResponse)
async def dataset_upload_start(
    dataset_slug: str, account: RequireUploader, session: SessionDep, request: Request
):
    """Partial to allow an initial upload and validation of a torrent file"""
    dataset = crud.get_dataset(session=session, dataset_slug=dataset_slug)
    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"No such dataset {dataset_slug} exists",
        )
    if not dataset.enabled:
        raise HTTPException(
            status_code=401,
            detail=f"Dataset {dataset_slug} is not enabled for upload",
        )

    return templates.TemplateResponse(
        "partials/upload-start.html",
        {"request": request, "config": config, "current_account": account, "dataset": dataset},
    )


@datasets_router.post("/{dataset_slug}/upload/torrent", response_class=HTMLResponse)
async def dataset_upload_torrent(
    dataset_slug: str,
    file: Annotated[UploadFile, File()],
    account: RequireUploader,
    session: SessionDep,
    request: Request,
):
    """Validate and create a torrent file,"""
    dataset = crud.get_dataset(session=session, dataset_slug=dataset_slug)
    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"No such dataset {dataset_slug} exists",
        )
    if not dataset.enabled:
        raise HTTPException(
            status_code=401,
            detail=f"Dataset {dataset_slug} is not enabled for upload",
        )

    created_torrent = await upload_torrent(account=account, file=file, session=session)

    return templates.TemplateResponse(
        "partials/upload-complete.html",
        {
            "request": request,
            "config": config,
            "current_account": account,
            "dataset": dataset,
            "torrent": created_torrent,
            "model": UploadCreate,
        },
    )
