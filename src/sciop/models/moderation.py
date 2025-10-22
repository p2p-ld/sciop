from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Optional

from annotated_types import doc
from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import RelationshipProperty
from sqlmodel import Field, Relationship

from sciop.models.base import SQLModel
from sciop.models.mixins import TableMixin
from sciop.types import IDField, UTCDateTime

if TYPE_CHECKING:
    from sciop.models import Account, AccountRead, Dataset, DatasetPart, Upload, Webseed


class ModerationAction(StrEnum):
    request = "request"
    """Request some permission or action"""
    approve = "approve"
    """Approve a request - e.g. a dataset or upload request"""
    unapprove = "unapprove"
    """Unapprove an already accepted request - e.g. a dataset or upload request"""
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
    suspend_remove = "suspend_remove"
    """Suspend an account and remove all its associated content"""
    restore = "restore"
    """Restore a suspended account"""
    remove = "remove"
    """Remove an item"""
    hide = "hide"
    """Hide an item"""


class ReportAction(StrEnum):
    """
    Can't subset an enum,
    so this is a manual subset of moderation actions that apply to report resolutions.
    """

    dismiss: Annotated[str, doc("Dismiss a report, taking no action.")] = "dismiss"
    hide: Annotated[
        str,
        doc(
            "Hide an item by marking it as unapproved. The item is retained, "
            "but is only visible to moderators and the creator. "
            "This returns the item to the moderation queue, "
            "and is usually used when some change is needed but the item is otherwise salvageable."
        ),
    ] = "hide"
    remove: Annotated[str, doc("Permanently remove an item, upholding the report.")] = "remove"
    suspend: Annotated[
        str,
        doc(
            "Suspend the reported account or the account that created the reported item. "
            "If the report was for an item, that item will also be removed, "
            "but an account's other created items will remain unchanged."
        ),
    ] = "suspend"
    suspend_remove: Annotated[
        str, doc("Suspend the account AND remove all items created by this account.")
    ] = "suspend_remove"

    @classmethod
    def get_base_action(self, action: str) -> ModerationAction:
        return ModerationAction.__members__[action]


_actor_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=True, index=True)
_target_account_id = Column(
    Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True, index=True
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
        default=None, foreign_key="datasets.dataset_id", ondelete="SET NULL", index=True
    )
    target_dataset: Optional["Dataset"] = Relationship(
        back_populates="audit_log_target", sa_relationship_kwargs={"lazy": "selectin"}
    )
    target_dataset_part_id: Optional[int] = Field(
        default=None, foreign_key="dataset_parts.dataset_part_id", ondelete="SET NULL", index=True
    )
    target_dataset_part: Optional["DatasetPart"] = Relationship(
        back_populates="audit_log_target", sa_relationship_kwargs={"lazy": "selectin"}
    )
    target_upload_id: Optional[int] = Field(
        default=None, foreign_key="uploads.upload_id", ondelete="SET NULL", index=True
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
    target_webseed_id: Optional[int] = Field(
        default=None, foreign_key="webseeds.webseed_id", ondelete="SET NULL", index=True
    )
    target_webseed: Optional["Webseed"] = Relationship(
        back_populates="audit_log_target", sa_relationship_kwargs={"lazy": "selectin"}
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
    target_dataset_part: Optional["DatasetPart"] = None
    target_upload: Optional["Upload"] = None
    target_webseed: Optional["Webseed"] = None
    value: Optional[str] = None
    created_at: UTCDateTime
    updated_at: UTCDateTime
