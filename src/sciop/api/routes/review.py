from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Response

from sciop import crud
from sciop.api.auth import create_access_token
from sciop.api.deps import SessionDep, RequireReviewer
from sciop.config import config
from sciop.models import Account, AccountCreate, Token, Dataset, SuccessResponse
from sciop.logging import init_logger

review_router = APIRouter(prefix="/review")


@review_router.post("/datasets/{dataset_slug}/approve")
def approve_dataset(
    dataset_slug: str, account: RequireReviewer, session: SessionDep
) -> SuccessResponse:
    dataset = crud.get_dataset(dataset_slug=dataset_slug, session=session)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset does not exist!")

    logger = init_logger("api.review")
    logger.info(f"{account.username} - Approving dataset {dataset_slug}")
    dataset.enabled = True
    session.add(dataset)
    session.commit()
    return SuccessResponse(success=True)
