from enum import StrEnum
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

from sciop.models.mixin import TableMixin

if TYPE_CHECKING:
    from sciop.models import Account


class ModerationAction(StrEnum):
    request = "request"
    """Request some permission or action"""
    approve = "approve"
    """Approve a request - e.g. a dataset or upload request"""
    deny = "deny"
    """Deny a request, as above"""
    report = "report"
    """Report an item"""
    add_scope = "add"
    """Add, e.g. a scope to an account"""
    remove_scope = "remove"
    """Remove an item - a dataset, upload, account scope etc."""
    dismiss = "dismiss"
    """Dismiss a report without action"""
    trust = "trust"
    """Increment trust value"""
    distrust = "distrust"
    """Decrement trust value"""


class AuditLog(TableMixin, table=True):
    """
    Moderation actions

    References to target columns do not have foreign key constraints
    so that if e.g. an account or dataset is deleted, the moderation action is not.
    """

    actor: "Account" = Relationship(back_populates="moderation_actions")
    actor_id: Optional[int] = Field(default=None, foreign_key="account.id")
    action: ModerationAction = Field(description="The action taken")
    dataset_id: Optional[int] = Field(description="Target dataset ID, if any")
    account_id: Optional[int] = Field(description="Target account ID, if any")
    upload_id: Optional[int] = Field(description="Target upload ID, if any")
    value: Optional[str] = Field(
        None,
        description="The value of the action, if any, e.g. the scope added to an account",
    )


class Report(TableMixin, table=True):
    """Reports of items and accounts"""
