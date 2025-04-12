from typing import Annotated, Optional
from typing import Literal as L
from urllib.parse import parse_qsl, urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from fasthx.dependencies import DependsHXRequest
from sqlmodel import Session, select
from starlette.datastructures import QueryParams
from starlette.requests import Request
from starlette.responses import Response

from sciop import crud
from sciop.api.deps import (
    CurrentAccount,
    RequireCurrentAccount,
    RequireEditableBy,
    RequireVisibleDataset,
    RequireVisibleDatasetPart,
    SessionDep,
)
from sciop.api.routes.upload import upload_torrent
from sciop.frontend.templates import jinja, templates
from sciop.models import Dataset, DatasetRead, DatasetUpdate, SearchParams, UploadCreate

datasets_router = APIRouter(prefix="/datasets")


def parse_query(search: Annotated[SearchParams, Query()], request: Request) -> SearchParams:
    if "hx-current-url" in request.headers:
        current_params = parse_qsl(urlparse(request.headers["hx-current-url"]).query)
        query_params = QueryParams(current_params + request.query_params._list)
    else:
        query_params = request.query_params
    return SearchParams.from_query_params(query_params)


SearchQuery = Annotated[SearchParams, Depends(parse_query)]


@datasets_router.get("/", response_class=HTMLResponse)
async def datasets(request: Request, search: Annotated[SearchQuery, Query()]):
    query_str = search.to_query_str()
    return templates.TemplateResponse(request, "pages/datasets.html", {"query_str": query_str})


@datasets_router.get("/search")
@jinja.hx("partials/datasets.html")
async def datasets_search(
    search: SearchQuery,
    session: SessionDep,
    current_account: CurrentAccount,
    request: Request,
    response: Response,
) -> Page[DatasetRead]:
    if not search.query or len(search.query) < 3:
        stmt = select(Dataset).where(Dataset.visible_to(current_account) == True)
        if not search.sort:
            stmt = stmt.order_by(Dataset.created_at.desc())
    else:
        stmt = Dataset.search(search.query).where(Dataset.visible_to(current_account) == True)

    stmt = search.apply_sort(stmt, model=Dataset)
    if search.should_redirect():
        print(search.to_query_str())
        response.headers["HX-Replace-Url"] = f"{search.to_query_str()}"
    else:
        response.headers["HX-Replace-Url"] = "/datasets/"

    return paginate(conn=session, query=stmt)


@datasets_router.get("/{dataset_slug}", response_class=HTMLResponse)
async def dataset_show(
    dataset_slug: str, dataset: RequireVisibleDataset, session: SessionDep, request: Request
):
    return templates.TemplateResponse(request, "pages/dataset.html", {"dataset": dataset})


@datasets_router.get("/{dataset_slug}/edit", response_class=HTMLResponse)
async def dataset_edit(
    dataset_slug: str,
    dataset: RequireVisibleDataset,
    current_account: RequireEditableBy,
    request: Request,
):
    dataset_update = DatasetUpdate.from_dataset(dataset)
    return templates.TemplateResponse(
        request, "pages/dataset-edit.html", {"dataset": dataset_update}
    )


@datasets_router.get("/{dataset_slug}/partial", response_class=HTMLResponse)
async def dataset_partial(
    dataset_slug: str,
    request: Request,
    dataset: RequireVisibleDataset,
):
    return templates.TemplateResponse(request, "partials/dataset.html", {"dataset": dataset})


@datasets_router.get("/{dataset_slug}/parts", response_class=HTMLResponse)
async def dataset_parts(
    dataset_slug: str,
    request: Request,
    dataset: RequireVisibleDataset,
    current_account: CurrentAccount,
):
    parts = [
        p
        for p in sorted(dataset.parts, key=lambda pt: pt.part_slug)
        if p.visible_to(current_account)
    ]
    return templates.TemplateResponse(
        request, "partials/dataset-parts.html", {"dataset": dataset, "parts": parts}
    )


@datasets_router.get("/{dataset_slug}/parts/add", response_class=HTMLResponse)
async def dataset_part_add_partial(
    dataset_slug: str,
    request: Request,
    dataset: RequireVisibleDataset,
    mode: Annotated[L["bulk"] | L["one"], Query()] = "one",
):
    return templates.TemplateResponse(
        request, "partials/dataset-part-add.html", {"dataset": dataset, "mode": mode}
    )


@datasets_router.get("/{dataset_slug}/uploads", response_class=HTMLResponse)
async def dataset_uploads(
    dataset_slug: str,
    dataset: RequireVisibleDataset,
    session: SessionDep,
    request: Request,
):
    uploads = crud.get_visible_uploads(dataset=dataset, session=session)
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
    account: RequireCurrentAccount,
    session: SessionDep,
    dataset: RequireVisibleDataset,
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
    dataset: RequireVisibleDataset,
    file: Annotated[UploadFile, File()],
    account: RequireCurrentAccount,
    session: SessionDep,
    request: Request,
    response: Response,
    hx_request: DependsHXRequest,
):
    """Validate and create a torrent file,"""

    created_torrent = await upload_torrent(
        account=account,
        file=file,
        session=session,
        request=request,
        response=response,
        __hx_request=None,
    )
    parts = _parts_from_query(query=request.query_params, dataset=dataset, session=session)

    return templates.TemplateResponse(
        request,
        "partials/upload-complete.html",
        {"dataset": dataset, "torrent": created_torrent, "model": UploadCreate, "parts": parts},
    )


@datasets_router.get("/{dataset_slug}/{dataset_part_slug}", response_class=HTMLResponse)
async def dataset_part_show(
    dataset_slug: str,
    dataset_part_slug: str,
    request: Request,
    dataset: RequireVisibleDataset,
    part: RequireVisibleDatasetPart,
    session: SessionDep,
):
    return templates.TemplateResponse(
        request, "pages/dataset-part.html", {"dataset": dataset, "part": part}
    )


@datasets_router.get("/{dataset_slug}/{dataset_part_slug}/partial", response_class=HTMLResponse)
async def dataset_part_partial(
    dataset_slug: str,
    dataset_part_slug: str,
    request: Request,
    dataset: RequireVisibleDataset,
    part: RequireVisibleDatasetPart,
    session: SessionDep,
):
    return templates.TemplateResponse(
        request, "partials/dataset-part.html", {"dataset": dataset, "part": part}
    )


@datasets_router.get("/{dataset_slug}/{dataset_part_slug}/uploads", response_class=HTMLResponse)
async def dataset_part_uploads(
    dataset_slug: str,
    dataset_part_slug: str,
    request: Request,
    part: RequireVisibleDatasetPart,
    session: SessionDep,
):
    uploads = crud.get_visible_uploads(dataset=part, session=session)
    return templates.TemplateResponse(
        request,
        "partials/dataset-uploads.html",
        {"uploads": uploads},
    )
