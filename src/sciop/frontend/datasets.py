from typing import Annotated, Optional
from typing import Literal as L

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import Session, select
from starlette.datastructures import QueryParams

from sciop import crud
from sciop.api.deps import (
    CurrentAccount,
    RequireApprovedDataset,
    RequireDataset,
    RequireDatasetPart,
    RequireUploader,
    SessionDep,
)
from sciop.api.routes.upload import upload_torrent
from sciop.frontend.templates import jinja, templates
from sciop.models import Dataset, DatasetRead, UploadCreate

datasets_router = APIRouter(prefix="/datasets")


@datasets_router.get("/", response_class=HTMLResponse)
async def datasets(request: Request):
    return templates.TemplateResponse(request, "pages/datasets.html")


@datasets_router.get("/search")
@jinja.hx("partials/datasets.html")
async def datasets_search(query: str = None, session: SessionDep = None) -> Page[DatasetRead]:
    if not query or len(query) < 3:
        stmt = (
            select(Dataset).where(Dataset.is_approved == True).order_by(Dataset.created_at.desc())
        )
    else:
        stmt = (
            select(Dataset)
            .where(Dataset.is_approved == True)
            .filter(Dataset.dataset_id.in_(Dataset.search_statement(query)))
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
    return templates.TemplateResponse(request, "pages/dataset.html", {"dataset": dataset})


@datasets_router.get("/{dataset_slug}/partial", response_class=HTMLResponse)
async def dataset_partial(request: Request, dataset: RequireDataset):
    return templates.TemplateResponse(request, "partials/dataset.html", {"dataset": dataset})


@datasets_router.get("/{dataset_slug}/parts", response_class=HTMLResponse)
async def dataset_parts(request: Request, dataset: RequireDataset):
    return templates.TemplateResponse(
        request, "partials/dataset-parts.html", {"dataset": dataset, "parts": dataset.parts}
    )


@datasets_router.get("/{dataset_slug}/parts/add", response_class=HTMLResponse)
async def dataset_part_add_partial(
    request: Request,
    dataset: RequireDataset,
    mode: Annotated[L["bulk"] | L["one"], Query()] = "one",
):
    return templates.TemplateResponse(
        request, "partials/dataset-part-add.html", {"dataset": dataset, "mode": mode}
    )


@datasets_router.get("/{dataset_slug}/uploads", response_class=HTMLResponse)
async def dataset_uploads(
    dataset_slug: str,
    dataset: RequireDataset,
    session: SessionDep,
    request: Request,
):
    uploads = crud.get_uploads(dataset=dataset, session=session)
    return templates.TemplateResponse(
        request,
        "partials/dataset-uploads.html",
        {"uploads": uploads, "dataset": dataset},
    )


def _parts_from_query(
    query: QueryParams, dataset: Dataset, session: Session
) -> Optional[list[str]]:
    parts = list(query.keys())
    if parts:
        existing_parts = crud.check_existing_dataset_parts(
            session=session, dataset=dataset, part_slugs=parts
        )
        if extra_parts := set(parts) - set(existing_parts):
            raise HTTPException(404, f"Parts do not exist: {extra_parts}")
        return parts
    else:
        return None


@datasets_router.get("/{dataset_slug}/upload/start", response_class=HTMLResponse)
async def dataset_upload_start(
    dataset_slug: str,
    account: RequireUploader,
    session: SessionDep,
    dataset: RequireApprovedDataset,
    request: Request,
):
    """
    Partial to allow an initial upload and validation of a torrent file

    Query parameters are assumed to be dataset parts, annoyingly passed like
    `part-slug=on&part-slug-2=on`, so we just interpret the keys
    """
    parts = _parts_from_query(query=request.query_params, dataset=dataset, session=session)
    return templates.TemplateResponse(
        request, "partials/upload-start.html", {"dataset": dataset, "parts": parts}
    )


@datasets_router.post("/{dataset_slug}/upload/torrent", response_class=HTMLResponse)
async def dataset_upload_torrent(
    dataset_slug: str,
    dataset: RequireApprovedDataset,
    file: Annotated[UploadFile, File()],
    account: RequireUploader,
    session: SessionDep,
    request: Request,
):
    """Validate and create a torrent file,"""

    created_torrent = await upload_torrent(account=account, file=file, session=session)
    parts = _parts_from_query(query=request.query_params, dataset=dataset, session=session)

    return templates.TemplateResponse(
        request,
        "partials/upload-complete.html",
        {"dataset": dataset, "torrent": created_torrent, "model": UploadCreate, "parts": parts},
    )


@datasets_router.get("/{dataset_slug}/{dataset_part_slug}", response_class=HTMLResponse)
async def dataset_part_show(
    request: Request, dataset: RequireDataset, part: RequireDatasetPart, session: SessionDep
):
    return templates.TemplateResponse(
        request, "pages/dataset-part.html", {"dataset": dataset, "part": part}
    )


@datasets_router.get("/{dataset_slug}/{dataset_part_slug}/partial", response_class=HTMLResponse)
async def dataset_part_partial(
    request: Request, dataset: RequireDataset, part: RequireDatasetPart, session: SessionDep
):
    return templates.TemplateResponse(
        request, "partials/dataset-part.html", {"dataset": dataset, "part": part}
    )


@datasets_router.get("/{dataset_slug}/{dataset_part_slug}/uploads", response_class=HTMLResponse)
async def dataset_part_uploads(
    request: Request, dataset_slug: str, part: RequireDatasetPart, session: SessionDep
):
    uploads = crud.get_uploads(dataset=part, session=session)
    return templates.TemplateResponse(
        request,
        "partials/dataset-uploads.html",
        {"uploads": uploads},
    )
