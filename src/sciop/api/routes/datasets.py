from typing import Annotated

from fastapi import APIRouter, Body, Form, HTTPException
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select
from starlette.requests import Request
from starlette.responses import Response

from sciop import crud
from sciop.api.deps import (
    CurrentAccount,
    RequireCurrentAccount,
    RequireDataset,
    RequireDatasetPart,
    RequireEnabledDataset,
    RequireUploader,
    SessionDep,
)
from sciop.middleware import limiter
from sciop.models import (
    Dataset,
    DatasetCreate,
    DatasetPart,
    DatasetPartCreate,
    DatasetPartRead,
    DatasetRead,
    Upload,
    UploadCreate,
)
from sciop.types import SlugStr

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
    response.headers["HX-Location"] = f"/datasets/{created_dataset.slug}"
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

    TODO: This can likely be removed after the addition of form-json
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


@datasets_router.get("/{dataset_slug}")
async def dataset_show(dataset: RequireDataset) -> DatasetRead:
    return dataset


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


@datasets_router.get("/{dataset_slug}/parts")
async def part_show_bulk(dataset: RequireDataset, account: CurrentAccount) -> list[DatasetPartRead]:
    if account and account.has_scope("review"):
        return dataset.parts
    else:
        return [p for p in dataset.parts if p.enabled]


@datasets_router.post("/{dataset_slug}/parts")
async def part_create_bulk(
    parts: Annotated[list[SlugStr] | list[DatasetPartCreate] | DatasetPartCreate, Body()],
    account: RequireCurrentAccount,
    dataset: RequireDataset,
    session: SessionDep,
) -> list[DatasetPartRead]:
    """
    Create dataset parts in bulk

    Either a list of `part_slugs` with no paths, or a list of slugs with paths
    """
    # casting to strs first is cheaper than pydantic before we have validated existence
    if not isinstance(parts, list):
        parts = [parts]
    slugs = [p if isinstance(p, str) else p.part_slug for p in parts]
    stmt = select(DatasetPart.part_slug).join(Dataset).filter(DatasetPart.part_slug.in_(slugs))
    print(stmt.compile())
    existing_parts = session.exec(stmt).all()
    if existing_parts:
        raise HTTPException(
            400,
            detail=f"Dataset parts for {dataset.slug} with the following slugs already exist: "
            f"{existing_parts}",
        )

    # now we create the models after we know it's fine to do
    parts = [DatasetPartCreate(part_slug=p) if isinstance(p, str) else p for p in parts]

    created_parts = [
        crud.create_dataset_part(
            session=session, dataset_part=p, dataset=dataset, account=account, commit=False
        )
        for p in parts
    ]
    session.commit()
    created_parts = [session.refresh(p) for p in created_parts]
    return created_parts


@datasets_router.get("/{dataset_slug}/parts/{part_slug}")
async def part_show(
    dataset_slug: str, part_slug: str, account: CurrentAccount, part: RequireDatasetPart
) -> DatasetPartRead:
    if not part.enabled and (not account or not account.has_scope("review")):
        raise HTTPException(
            status_code=404,
            detail=f"No such dataset part {dataset_slug}/{part_slug} exists!",
        )
    return part


@datasets_router.post("/{dataset_slug}/parts/{part_slug}")
async def part_create_one(
    dataset_slug: str,
    part_slug: str,
    account: RequireCurrentAccount,
    dataset: RequireDataset,
    session: SessionDep,
    paths: list[str] | None = None,
) -> DatasetPartRead:
    """create a single dataset part"""
    existing_part = crud.get_dataset_part(
        session=session, dataset_slug=dataset_slug, dataset_part_slug=part_slug
    )
    if existing_part:
        raise HTTPException(400, f"Dataset part {part_slug} for {dataset_slug} already exists!")
    created_part = (
        DatasetPartCreate(part_slug=part_slug, paths=paths)
        if paths
        else DatasetPartCreate(part_slug=part_slug)
    )
    return crud.create_dataset_part(
        session=session, dataset=dataset, account=account, dataset_part=created_part
    )
