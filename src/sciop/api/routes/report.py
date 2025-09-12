from fastapi import APIRouter, HTTPException

from sciop import crud
from sciop.api.deps import RequireCurrentAccount, SessionDep
from sciop.models import ReportCreate, ReportRead

report_router = APIRouter(prefix="/reports")


@report_router.post("/")
async def create_report(
    current_account: RequireCurrentAccount, report: ReportCreate, session: SessionDep
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
    return created
