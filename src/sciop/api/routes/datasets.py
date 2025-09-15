import sys
from typing import Annotated

if sys.version_info < (3, 12):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict

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
    RequireEditableBy,
    RequireScopableDataset,
    RequireVisibleDataset,
    RequireVisibleDatasetPart,
    SessionDep,
)
from sciop.api.routes.uploads import create_upload
from sciop.frontend.templates import jinja
from sciop.middleware import limiter
from sciop.models import (
    Dataset,
    DatasetCreate,
    DatasetPartCreate,
    DatasetPartRead,
    DatasetRead,
    DatasetUpdate,
    Upload,
    UploadCreate,
    UploadRead,
)
from sciop.types import ModerationAction, SlugStr

datasets_router = APIRouter(prefix="/datasets")


@datasets_router.get("/")
async def datasets(session: SessionDep, current_account: CurrentAccount) -> Page[DatasetRead]:
    return paginate(
        session,
        select(Dataset)
        .where(Dataset.visible_to(current_account) == True)
        .order_by(Dataset.created_at),
    )


@datasets_router.post("/")
@limiter.limit("10/hour")
async def datasets_create(
    request: Request,
    dataset: DatasetCreate,
    session: SessionDep,
    current_account: RequireCurrentAccount,
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
    current_account: RequireCurrentAccount,
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
async def dataset_show(dataset_slug: str, dataset: RequireDataset) -> DatasetRead:
    return dataset


@datasets_router.patch("/{dataset_slug}")
async def dataset_edit(
    dataset_slug: str,
    dataset_patch: Annotated[DatasetUpdate, Body()],
    dataset: RequireScopableDataset,
    current_account: RequireEditableBy,
    session: SessionDep,
    request: Request,
    response: Response,
) -> DatasetRead:
    """Edit a dataset!"""
    updated_dataset = dataset.update(session, new=dataset_patch, commit=True)
    if "HX-Request" in request.headers:
        response.headers["HX-Redirect"] = f"/datasets/{updated_dataset.slug}"
    return updated_dataset


@datasets_router.delete("/{dataset_slug}")
async def dataset_delete(
    dataset_slug: str,
    session: SessionDep,
    current_account: RequireCurrentAccount,
    dataset: RequireDataset,
):
    if not dataset.removable_by(current_account):
        raise HTTPException(403, f"Not permitted to remove dataset {dataset.slug}")
    dataset.is_removed = True
    session.add(dataset)
    session.commit()
    crud.log_moderation_action(
        session=session, actor=current_account, target=dataset, action=ModerationAction.remove
    )


@datasets_router.post("/{dataset_slug}/uploads")
async def datasets_create_upload(
    upload: UploadCreate,
    dataset_slug: str,
    dataset: RequireVisibleDataset,
    account: RequireCurrentAccount,
    session: SessionDep,
) -> UploadRead:
    """Create an upload of a dataset"""
    upload.dataset_slug = dataset_slug
    return await create_upload(session=session, upload=upload, current_account=account)


@datasets_router.post("/{dataset_slug}/uploads/form")
async def datasets_create_upload_form(
    upload: Annotated[UploadCreate, Form()],
    dataset_slug: str,
    dataset: RequireVisibleDataset,
    account: RequireCurrentAccount,
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
    response.headers["HX-Redirect"] = f"/uploads/{created_upload.infohash}"
    return created_upload


@datasets_router.get("/{dataset_slug}/parts")
async def part_show_bulk(
    dataset_slug: str, dataset: RequireDataset, account: CurrentAccount
) -> list[DatasetPartRead]:
    return [p for p in dataset.parts if p.visible_to(account)]


@datasets_router.post("/{dataset_slug}/parts")
@jinja.hx("partials/dataset-part.html")
async def part_create(
    dataset_slug: str,
    parts: Annotated[list[SlugStr] | list[DatasetPartCreate] | DatasetPartCreate, Body()],
    account: RequireCurrentAccount,
    dataset: RequireDataset,
    session: SessionDep,
    request: Request,
) -> list[DatasetPartRead]:
    """
    Create dataset part or multiple parts

    Either a single DatasetPart, a list of DatasetParts, or a list of `part_slugs` with no paths.

    If a string, assumed to be a newline separated list of slugs
    (e.g. as submitted by a textinput form)
    """
    if isinstance(parts, str):
        parts = [p.strip() for p in parts.split("\n") if p.strip()]
    elif not isinstance(parts, list):
        parts = [parts]
    # casting to strs first is cheaper than pydantic before we have validated existence

    existing_parts = crud.check_existing_dataset_parts(
        session=session, dataset=dataset, part_slugs=parts
    )
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
    for p in created_parts:
        session.refresh(p)
    if "hx-request" in request.headers:
        return {"parts": created_parts, "dataset": dataset}
    else:
        return created_parts


@datasets_router.post("/{dataset_slug}/parts_bulk", include_in_schema=False)
@jinja.hx("partials/dataset-part.html")
async def _part_create_bulk(
    dataset_slug: str,
    parts: Annotated[TypedDict("parts", {"parts": str}), Body()],
    account: RequireCurrentAccount,
    dataset: RequireDataset,
    session: SessionDep,
    request: Request,
) -> list[DatasetPartRead]:
    """
    Special method for creating bulk parts from form input,
    which fastAPI doesn't handle as body input.

    Not intended to be part of the public API.
    """
    parts = parts["parts"]
    parts = [p.strip() for p in parts.split("\n") if p.strip()]
    return await part_create(
        dataset_slug=dataset_slug,
        parts=parts,
        account=account,
        dataset=dataset,
        session=session,
        request=request,
        __hx_request=request,
    )


@datasets_router.get("/{dataset_slug}/parts/{part_slug}")
async def part_show(
    dataset_slug: str, part_slug: str, part: RequireVisibleDatasetPart
) -> DatasetPartRead:
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
