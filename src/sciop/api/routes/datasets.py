from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Response
from fastapi_pagination import Page, paginate
from fastapi_pagination.ext.sqlalchemy import paginate

from sciop import crud
from sciop.api.auth import create_access_token
from sciop.api.deps import SessionDep, CurrentAccount
from sciop.config import config
from sciop import crud
from sciop.models import Account, AccountCreate, Token, Dataset, DatasetRead, DatasetCreate
from sqlmodel import select

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


# @datasets_router.post("/form")
# def datasets_create_form(
#
# )

# Annotated[DatasetCreate, Form()] |
