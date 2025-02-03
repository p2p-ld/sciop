from fastapi import APIRouter

from sciop.frontend.index import index_router
from sciop.frontend.datasets import datasets_router
from sciop.frontend.review import review_router

frontend_router = APIRouter()
frontend_router.include_router(index_router)
frontend_router.include_router(datasets_router)
frontend_router.include_router(review_router)
