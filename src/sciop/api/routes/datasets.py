from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop import crud
from sciop.api.deps import CurrentAccount, RequireEnabledDataset, RequireUploader, SessionDep
from sciop.models import (
    Dataset,
    DatasetCreate,
    DatasetInstance,
    DatasetInstanceCreate,
    DatasetRead,
)

datasets_router = APIRouter(prefix="/datasets")


@datasets_router.get("/")
def datasets(session: SessionDep) -> Page[DatasetRead]:
    return paginate(session, select(Dataset).order_by(Dataset.created_at))


@datasets_router.post("/")
def datasets_create(
    dataset: DatasetCreate, session: SessionDep, current_account: CurrentAccount
) -> DatasetRead:
    existing_dataset = crud.get_dataset(session=session, dataset_slug=dataset.slug)
    if existing_dataset:
        raise HTTPException(
            status_code=400,
            detail="A dataset with this slug already exists!",
        )
    created_dataset = crud.create_dataset(
        session=session, dataset_create=dataset, current_account=current_account
    )
    return created_dataset


@datasets_router.post("/form")
def datasets_create_form(
    dataset: Annotated[DatasetCreate, Form()],
    session: SessionDep,
    current_account: CurrentAccount,
    response: Response,
) -> DatasetRead:
    """
    Create a dataset with form encoded data
    """
    created_dataset = datasets_create(
        dataset=dataset, session=session, current_account=current_account
    )
    response.headers["HX-Location"] = f"/datasets/{created_dataset.slug}"
    return created_dataset


@datasets_router.post("/{dataset_slug}/instances")
def datasets_create_instance(
    instance: DatasetInstanceCreate,
    dataset_slug: str,
    dataset: RequireEnabledDataset,
    account: RequireUploader,
    session: SessionDep,
) -> DatasetInstance:
    """Create an instance of a dataset"""
    torrent = crud.get_torrent_from_short_hash(
        session=session, short_hash=instance.torrent_short_hash
    )
    if not torrent:
        raise HTTPException(
            status_code=404,
            detail=f"No torrent with short hash {instance.torrent_short_hash} exists, "
            "upload it first!",
        )
    created_instance = crud.create_instance(
        session=session, created_instance=instance, dataset=dataset, account=account
    )
    return created_instance


@datasets_router.post("/{dataset_slug}/instances/form")
def datasets_create_instance_form(
    instance: Annotated[DatasetInstanceCreate, Form()],
    dataset_slug: str,
    dataset: RequireEnabledDataset,
    account: RequireUploader,
    session: SessionDep,
    response: Response,
) -> DatasetInstance:
    """Create an instance of a dataset"""
    created_instance = datasets_create_instance(
        instance=instance,
        dataset_slug=dataset_slug,
        dataset=dataset,
        account=account,
        session=session,
    )
    response.headers["HX-Refresh"] = "true"
    return created_instance


# @datasets_router.post("/form")
# def datasets_create_form(
#
# )

# Annotated[DatasetCreate, Form()] |
