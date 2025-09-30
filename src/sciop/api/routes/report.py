from fastapi import APIRouter, HTTPException, Request
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop import crud
from sciop.api.deps import RequireCurrentAccount, RequireReport, SearchQueryNoCurrentUrl, SessionDep
from sciop.frontend.templates import jinja, passthrough_context
from sciop.middleware import limiter
from sciop.models import Report, ReportCreate, ReportRead, SearchPage

report_router = APIRouter(prefix="/reports")


@report_router.post("/")
@limiter.limit("20/hour")
@jinja.hx("partials/report-submitted.html")
async def create_report(
    current_account: RequireCurrentAccount,
    report: ReportCreate,
    session: SessionDep,
    request: Request,
) -> ReportRead:
    try:
        target = report.get_target(session)
    except Exception as e:
        raise HTTPException(
            422, "Error when trying to retrieve the target, check that it is specified correctly"
        ) from e

    if not target or not target.visible_to(current_account):
        raise HTTPException(404, "Target not found")

    created = crud.create_report(session=session, report=report, opened_by=current_account)
    return ReportRead.from_report(created)


@report_router.get("/")
@jinja.hx("partials/reports.html")
async def list_reports(
    current_account: RequireCurrentAccount,
    search: SearchQueryNoCurrentUrl,
    session: SessionDep,
) -> SearchPage[ReportRead]:
    stmt = (
        select(Report)
        .where(Report.visible_to(current_account) == True)
        .order_by(Report.created_at.desc())
    )
    stmt = search.apply_sort(stmt, Report)
    return paginate(query=stmt, conn=session)


@report_router.get("/{report_id}")
@jinja.hx("partials/report.html", make_context=passthrough_context("report"))
async def show_report(
    report_id: int,
    current_account: RequireCurrentAccount,
    report: RequireReport,
) -> ReportRead:
    return ReportRead.from_report(report)
