from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from sciop import crud
from sciop.api.deps import RequireReviewer, SessionDep
from sciop.config import config
from sciop.frontend.templates import templates

review_router = APIRouter(prefix="/review")


@review_router.get("/datasets", response_class=HTMLResponse)
async def datasets(request: Request, account: RequireReviewer, session: SessionDep):
    datasets = crud.get_review_datasets(session=session)
    return templates.TemplateResponse(
        "partials/review-datasets.html",
        {"request": request, "config": config, "current_account": account, "datasets": datasets},
    )


@review_router.get("/instances", response_class=HTMLResponse)
async def instances(request: Request, account: RequireReviewer, session: SessionDep):
    instances = crud.get_review_instances(session=session)
    return templates.TemplateResponse(
        "partials/review-instances.html",
        {"request": request, "config": config, "current_account": account, "instances": instances},
    )
