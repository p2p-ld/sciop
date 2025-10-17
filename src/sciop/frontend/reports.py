from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from sciop.api.deps import RequireReport
from sciop.frontend.templates import templates

reports_router = APIRouter(prefix="/reports")


@reports_router.get("/{report_id}", response_class=HTMLResponse)
async def show_report(report_id: int, report: RequireReport, request: Request):
    return templates.TemplateResponse(
        request, "pages/report.html", {"report": report, "target": report.target}
    )


@reports_router.get("/{report_id}/partial", response_class=HTMLResponse)
async def report_partial(report_id: int, report: RequireReport, request: Request):
    return templates.TemplateResponse(
        request, "partials/report.html", {"report": report, "target": report.target}
    )
