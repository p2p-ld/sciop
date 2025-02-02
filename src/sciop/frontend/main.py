from fastapi import APIRouter

from sciop.frontend.index import index_router

frontend_router = APIRouter()
frontend_router.include_router(index_router)
