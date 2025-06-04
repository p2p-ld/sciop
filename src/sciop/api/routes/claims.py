from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop.api.deps import (
    CurrentAccount,
    CurrentDatasetClaim,
    CurrentDatasetPartClaim,
    RequireCurrentAccount,
    RequireDatasetPartClaim,
    RequireVisibleDataset,
    RequireVisibleDatasetPart,
    SessionDep,
)
from sciop.models import (
    ClaimStatus,
    DatasetClaim,
    DatasetClaimCreate,
    DatasetClaimRead,
    DatasetPart,
    SuccessResponse,
)

claims_router = APIRouter(prefix="/claims")


@claims_router.get("/")
def show_all_claims(session: SessionDep) -> Page[DatasetClaimRead]:
    """Show all active dataset claims"""
    return paginate(
        session,
        select(DatasetClaim).order_by(DatasetClaim.created_at),
    )


@claims_router.get("/self")
def show_my_claims(
    session: SessionDep, current_account: RequireCurrentAccount
) -> Page[DatasetClaimRead]:
    """Show all active dataset claims belonging to an account"""
    return paginate(
        session,
        select(DatasetClaim)
        .where(DatasetClaim.account_id == current_account.account_id)
        .order_by(DatasetClaim.created_at),
    )


@claims_router.get("/datasets/{dataset_slug}")
def get_dataset_claims(
    dataset_slug: str,
    session: SessionDep,
    dataset: RequireVisibleDataset,
    exclude_parts: bool = False,
) -> Page[DatasetClaimRead]:
    """Show all active claims against a dataset, including its parts (unless explicitly excluded)"""
    if exclude_parts:
        stmt = select(DatasetClaim).where(
            DatasetClaim.dataset == dataset, DatasetClaim.dataset_part == None  # noqa: E711
        )
    else:
        stmt = select(DatasetClaim).where(DatasetClaim.dataset == dataset)

    stmt = stmt.order_by(DatasetClaim.created_at)
    return paginate(session, stmt)


@claims_router.get("/datasets/{dataset_slug}/parts/{dataset_part_slug}")
def get_dataset_part_claims(
    dataset_slug: str,
    dataset_part_slug: str,
    session: SessionDep,
    dataset_part: RequireVisibleDatasetPart,
) -> Page[DatasetClaimRead]:
    """Show all active claims against a dataset part"""
    return paginate(
        session,
        select(DatasetClaim)
        .where(DatasetClaim.dataset_part == dataset_part)
        .order_by(DatasetClaim.created_at),
    )


@claims_router.post("/datasets/{dataset_slug}")
def create_dataset_claim(
    dataset_slug: str,
    dataset: RequireVisibleDataset,
    session: SessionDep,
    current_account: RequireCurrentAccount,
    claim: CurrentDatasetClaim,
    claim_status: ClaimStatus = ClaimStatus.in_progress,
) -> DatasetClaimRead:
    """
    Create a new dataset claim, or update an existing one.

    Only one claim of any type can exist for a given account at once.
    Posting to a dataset updates the updated_at time.
    """
    if claim:
        claim.updated_at = datetime.now(UTC)
        claim.status = claim_status
    else:
        claim = DatasetClaim(account=current_account, dataset=dataset, status=claim_status)

    session.add(claim)
    session.commit()
    session.refresh(claim)
    return claim


@claims_router.post("/datasets/{dataset_slug}/parts/{dataset_part_slug}")
async def create_dataset_part_claim(
    dataset_slug: str,
    dataset_part_slug: str,
    dataset: RequireVisibleDataset,
    dataset_part: RequireVisibleDatasetPart,
    session: SessionDep,
    current_account: RequireCurrentAccount,
    claim: CurrentDatasetPartClaim,
    claim_status: DatasetClaimCreate | None = None,
) -> DatasetClaimRead:
    """
    Create a new dataset claim, or update an existing one.

    Only one claim of any type can exist for a given account at once.
    Posting to a dataset updates the updated_at time.
    """
    claim_status = ClaimStatus.in_progress if claim_status is None else claim_status.status
    if claim:
        claim.updated_at = datetime.now(UTC)
        claim.status = claim_status
    else:
        claim = DatasetClaim(
            account=current_account, dataset=dataset, dataset_part=dataset_part, status=claim_status
        )

    session.add(claim)
    session.commit()
    session.refresh(claim)
    return claim


@claims_router.delete("/datasets/{dataset_slug}/parts/{dataset_part_slug}")
def delete_dataset_part_claim(
    dataset_slug: str,
    dataset_part_slug: str,
    dataset: RequireVisibleDataset,
    dataset_part: RequireVisibleDatasetPart,
    session: SessionDep,
    current_account: RequireCurrentAccount,
    claim: RequireDatasetPartClaim,
) -> SuccessResponse:
    """Delete an existing dataset claim."""
    session.delete(claim)
    session.commit()
    return SuccessResponse(success=True)


@claims_router.post("/datasets/{dataset_slug}/next")
def get_next_unclaimed_part(
    dataset_slug: str,
    dataset: RequireVisibleDataset,
    current_account: CurrentAccount,
    session: SessionDep,
    claim: bool = True,
) -> DatasetClaimRead:
    """
    Get the next dataset part, if any, that has no in_progress or completed claims,
    and has no uploads
    """
    stmt = (
        select(DatasetPart)
        .where(
            DatasetPart.dataset == dataset,
            DatasetPart.visible_to(current_account) == True,
            ~DatasetPart.uploads.any(),
            ~DatasetPart.claims.any(),
        )
        .order_by(DatasetPart.part_slug)
    )
    next_part = session.exec(stmt).first()
    if not next_part:
        raise HTTPException(404, "No unclaimed dataset parts for this dataset!")

    if claim and not current_account:
        raise HTTPException(
            401,
            "Must be logged in to claim a dataset part. Set claim=false to just see the next part.",
        )

    claim = DatasetClaim(
        account=current_account,
        dataset=dataset,
        dataset_part=next_part,
        status=ClaimStatus.in_progress,
    )
    session.add(claim)
    session.commit()
    session.refresh(claim)
    return DatasetClaimRead.model_validate(claim)
