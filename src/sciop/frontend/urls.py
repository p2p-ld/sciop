from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import or_, select

from sciop.api.deps import CurrentAccount, SearchQuery, SessionDep
from sciop.frontend.templates import jinja, templates
from sciop.models import URL, Dataset, SearchPage, Upload

urls_router = APIRouter(prefix="/urls")


@urls_router.get("/", response_class=HTMLResponse)
async def urls(request: Request, search: SearchQuery):
    query_str = search.to_query_str()
    return templates.TemplateResponse(request, "pages/urls.html", {"query_str": query_str})


@urls_router.get("/search")
@jinja.hx("partials/urls.html")
async def urls_search(
    search: SearchQuery, session: SessionDep, current_account: CurrentAccount, response: Response
) -> SearchPage[URL]:
    if not search.query or len(search.query) < 3:
        stmt = select(URL).order_by(URL.url_id.desc())
    else:
        stmt = URL.search(search.query)

    # only show urls that are attached to something the account can see
    stmt = stmt.where(
        or_(
            URL.datasets.any(Dataset.visible_to(current_account) == True),
            URL.uploads.any(Upload.visible_to(current_account) == True),
        )
    )

    if search.should_redirect():
        response.headers["HX-Replace-Url"] = f"{search.to_query_str()}"
    else:
        response.headers["HX-Replace-Url"] = "/urls/"

    return paginate(conn=session, query=stmt)
