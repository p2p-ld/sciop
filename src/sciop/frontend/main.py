from fastapi import APIRouter, Depends

from sciop.api.deps import add_htmx_response_trigger
from sciop.frontend.accounts import accounts_router
from sciop.frontend.datasets import datasets_router
from sciop.frontend.index import index_router
from sciop.frontend.rdf import rdf_router, id_router
from sciop.frontend.rss import rss_router
from sciop.frontend.self import self_router
from sciop.frontend.uploads import uploads_router

frontend_router = APIRouter(dependencies=[Depends(add_htmx_response_trigger)])
frontend_router.include_router(index_router)
frontend_router.include_router(accounts_router)
frontend_router.include_router(datasets_router)
frontend_router.include_router(rss_router)
frontend_router.include_router(id_router)
frontend_router.include_router(rdf_router)

frontend_router.include_router(self_router)
frontend_router.include_router(uploads_router)
