from fastapi import APIRouter, Depends

from sciop.api.deps import add_htmx_response_trigger
from sciop.config import config
from sciop.frontend.accounts import accounts_router
from sciop.frontend.autocomplete import autocomplete_router
from sciop.frontend.datasets import datasets_router
from sciop.frontend.index import index_router
from sciop.frontend.partials import partials_router
from sciop.frontend.rdf import id_router, rdf_router
from sciop.frontend.rss import rss_router
from sciop.frontend.self import self_router
from sciop.frontend.test import test_router
from sciop.frontend.uploads import uploads_router

frontend_router = APIRouter(dependencies=[Depends(add_htmx_response_trigger)])
frontend_router.include_router(index_router)
frontend_router.include_router(accounts_router)
frontend_router.include_router(autocomplete_router)
frontend_router.include_router(datasets_router)
frontend_router.include_router(rss_router)
frontend_router.include_router(id_router)
frontend_router.include_router(partials_router)
frontend_router.include_router(rdf_router)

frontend_router.include_router(self_router)
frontend_router.include_router(uploads_router)

if config.env != "prod":
    frontend_router.include_router(test_router)
