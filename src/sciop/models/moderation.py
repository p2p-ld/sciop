from enum import StrEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import RelationshipProperty
from sqlmodel import Field, Relationship, SQLModel

from sciop.models.mixins import TableMixin
from sciop.types import IDField, UTCDateTime

if TYPE_CHECKING:
    from sciop.models import Account, AccountRead, Dataset, DatasetPart, Upload


class ModerationAction(StrEnum):
    request = "request"
    """Request some permission or action"""
    approve = "approve"
    """Approve a request - e.g. a dataset or upload request"""
    deny = "deny"
    """Deny a request, as above"""
    report = "report"
    """Report an item"""
    add_scope = "add_scope"
    """Add, e.g. a scope to an account"""
    remove_scope = "remove_scope"
    """Remove an item - a dataset, upload, account scope etc."""
    dismiss = "dismiss"
    """Dismiss a report without action"""
    trust = "trust"
    """Increment trust value"""
    distrust = "distrust"
    """Decrement trust value"""
    suspend = "suspend"
    """Suspend an account"""
    restore = "restore"
    """Restore a suspended account"""
    remove = "remove"
    """Remove an item"""


_actor_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=True)
_target_account_id = Column(
    Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True
)


class AuditLog(TableMixin, table=True):
    """
    Moderation actions

    References to target columns do not have foreign key constraints
    so that if e.g. an account or dataset is deleted, the moderation action is not.
    """

    __tablename__ = "audit_log"

    audit_log_id: IDField = Field(None, primary_key=True)
    actor_id: Optional[int] = Field(sa_column=_actor_id)
    actor: "Account" = Relationship(
        back_populates="moderation_actions",
        sa_relationship=RelationshipProperty(
            "Account", foreign_keys=[_actor_id], back_populates="moderation_actions"
        ),
    )

    action: ModerationAction = Field(description="The action taken")

    target_dataset_id: Optional[int] = Field(
        default=None, foreign_key="datasets.dataset_id", ondelete="SET NULL"
    )
    target_dataset: Optional["Dataset"] = Relationship(
        back_populates="audit_log_target", sa_relationship_kwargs={"lazy": "selectin"}
    )
    target_dataset_part_id: Optional[int] = Field(
        default=None, foreign_key="dataset_parts.dataset_part_id", ondelete="SET NULL"
    )
    target_dataset_part: Optional["DatasetPart"] = Relationship(
        back_populates="audit_log_target", sa_relationship_kwargs={"lazy": "selectin"}
    )
    target_upload_id: Optional[int] = Field(
        default=None, foreign_key="uploads.upload_id", ondelete="SET NULL"
    )
    target_upload: Optional["Upload"] = Relationship(
        back_populates="audit_log_target", sa_relationship_kwargs={"lazy": "selectin"}
    )
    target_account_id: Optional[int] = Field(sa_column=_target_account_id)
    target_account: Optional["Account"] = Relationship(
        back_populates="audit_log_target",
        sa_relationship=RelationshipProperty(
            "Account",
            foreign_keys=[_target_account_id],
            lazy="selectin",
            back_populates="audit_log_target",
        ),
    )
    value: Optional[str] = Field(
        None,
        description="The value of the action, if any, e.g. the scope added to an account",
    )


class AuditLogRead(SQLModel):
    actor: "AccountRead"
    action: ModerationAction
    target_account: Optional["AccountRead"] = None
    target_dataset: Optional["Dataset"] = None
    target_upload: Optional["Upload"] = None
    value: Optional[str] = None
    created_at: UTCDateTime
    updated_at: UTCDateTime


class Report(TableMixin, table=True):
    """Reports of items and accounts"""

    __tablename__ = "reports"

    report_id: IDField = Field(None, primary_key=True)
