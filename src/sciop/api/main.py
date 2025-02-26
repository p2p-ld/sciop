from fastapi import APIRouter, Depends

from sciop.api.deps import add_htmx_response_trigger
from sciop.api.routes.datasets import datasets_router
from sciop.api.routes.login import login_router
from sciop.api.routes.review import review_router
from sciop.api.routes.tags import tags_router
from sciop.api.routes.upload import upload_router
from sciop.config import config

api_router = APIRouter(
    prefix=config.api_prefix, dependencies=[Depends(add_htmx_response_trigger)], tags=["api"]
)
api_router.include_router(login_router)
api_router.include_router(datasets_router)
api_router.include_router(review_router)
api_router.include_router(tags_router)
api_router.include_router(upload_router)
