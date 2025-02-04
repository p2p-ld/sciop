from fastapi import APIRouter, HTTPException

from sciop import crud
from sciop.api.deps import RequireReviewer, SessionDep
from sciop.logging import init_logger
from sciop.models import SuccessResponse

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
