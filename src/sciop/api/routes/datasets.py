from typing import Annotated

from fastapi import APIRouter, Form, HTTPException
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select
from starlette.requests import Request
from starlette.responses import Response

from sciop import crud
from sciop.api.deps import CurrentAccount, RequireEnabledDataset, RequireUploader, SessionDep
from sciop.middleware import limiter
from sciop.models import (
    Dataset,
    DatasetCreate,
    DatasetRead,
    Upload,
    UploadCreate,
)

datasets_router = APIRouter(prefix="/datasets")


@datasets_router.get("/")
async def datasets(session: SessionDep) -> Page[DatasetRead]:
    return paginate(session, select(Dataset).order_by(Dataset.created_at))


@datasets_router.post("/")
@limiter.limit("10/hour")
async def datasets_create(
    request: Request,
    dataset: DatasetCreate,
    session: SessionDep,
    current_account: CurrentAccount,
    response: Response,
) -> DatasetRead:
    existing_dataset = crud.get_dataset(session=session, dataset_slug=dataset.slug)
    if existing_dataset:
        # mimic the pydantic error
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "type": "value_not_unique",
                    "loc": ["body", "slug"],
                    "msg": "A dataset with this slug already exists!",
                }
            ],
        )
    created_dataset = crud.create_dataset(
        session=session, dataset_create=dataset, current_account=current_account
    )
    return created_dataset


@datasets_router.post("/form")
@limiter.limit("10/hour")
async def datasets_create_form(
    request: Request,
    dataset: Annotated[DatasetCreate, Form()],
    session: SessionDep,
    current_account: CurrentAccount,
    response: Response,
) -> DatasetRead:
    """
    Create a dataset with form encoded data
    """
    # hacky workaround for checkboxes in forms
    # https://github.com/fastapi/fastapi/discussions/13380
    form = await request.form()
    dataset.source_available = "source_available" in form
    created_dataset = await datasets_create(
        request=request,
        dataset=dataset,
        session=session,
        current_account=current_account,
        response=response,
    )
    response.headers["HX-Location"] = f"/datasets/{created_dataset.slug}"
    return created_dataset


@datasets_router.post("/{dataset_slug}/uploads")
async def datasets_create_upload(
    upload: UploadCreate,
    dataset_slug: str,
    dataset: RequireEnabledDataset,
    account: RequireUploader,
    session: SessionDep,
) -> Upload:
    """Create an upload of a dataset"""
    torrent = crud.get_torrent_from_short_hash(
        session=session, short_hash=upload.torrent_short_hash
    )
    if not torrent:
        raise HTTPException(
            status_code=404,
            detail=f"No torrent with short hash {upload.torrent_short_hash} exists, "
            "upload it first!",
        )
    created_upload = crud.create_upload(
        session=session, created_upload=upload, dataset=dataset, account=account
    )
    return created_upload


@datasets_router.post("/{dataset_slug}/uploads/form")
async def datasets_create_upload_form(
    upload: Annotated[UploadCreate, Form()],
    dataset_slug: str,
    dataset: RequireEnabledDataset,
    account: RequireUploader,
    session: SessionDep,
    response: Response,
) -> Upload:
    """Create an upload of a dataset"""
    created_upload = await datasets_create_upload(
        upload=upload,
        dataset_slug=dataset_slug,
        dataset=dataset,
        account=account,
        session=session,
    )
    response.headers["HX-Refresh"] = "true"
    return created_upload


# @datasets_router.post("/form")
# def datasets_create_form(
#
# )

# Annotated[DatasetCreate, Form()] |
