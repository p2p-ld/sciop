from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import RelationshipProperty
from sqlmodel import Field, Relationship

from sciop.models.base import SQLModel
from sciop.models.mixins import TableMixin
from sciop.types import IDField, ModerationAction, UTCDateTime

if TYPE_CHECKING:
    from sciop.models import Account, AccountRead, Dataset, DatasetPart, Upload, Webseed

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
