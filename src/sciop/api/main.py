from fastapi import APIRouter

from sciop.api.routes import login_router
from sciop.api.routes.datasets import datasets_router
from sciop.api.routes.review import review_router
from sciop.config import config

api_router = APIRouter(prefix=config.api_prefix)
api_router.include_router(login_router)
api_router.include_router(datasets_router)
api_router.include_router(review_router)
