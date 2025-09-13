from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, Optional, TypeAlias, Union, get_args

from annotated_types import DocInfo, MaxLen, doc
from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import RelationshipProperty
from sqlmodel import Field, Relationship, Session

from sciop.models.base import SQLModel
from sciop.models.mixins import TableMixin
from sciop.models.moderation import ModerationAction
from sciop.types import IDField, InputType, UsernameStr

if TYPE_CHECKING:
    from sciop.models import (
        Account,
        AccountRead,
        Dataset,
        DatasetPart,
        DatasetPartRead,
        DatasetRead,
        Upload,
        UploadRead,
    )

TargetType = Literal["account", "dataset", "dataset_part", "upload"]
TargetModels: TypeAlias = Union["Account", "Dataset", "DatasetPart", "Upload"]
TargetModelsRead: TypeAlias = Union["AccountRead", "DatasetRead", "DatasetPartRead", "UploadRead"]


class ReportType(StrEnum):
    rules: Annotated[str, doc("This item breaks one or more instance rules")] = "rules"
    spam: Annotated[str, doc("Automated behavior, comments, uploads, etc.")] = "spam"
    malicious: Annotated[
        str,
        doc(
            "This item contains malicious software, "
            "or otherwise is intended to damage the recipient's system."
        ),
    ] = "malicious"
    fake: Annotated[
        str, doc("Contents of item are not as described, but not apparently malicious.")
    ] = "fake"
    incorrect: Annotated[
        str,
        doc(
            "Contents of item are as described and not apparently malicious, "
            "but are incorrect, incomplete, broken, etc."
        ),
    ] = "incorrect"
    duplicate: Annotated[
        str,
        doc(
            "Item is an identical duplicate of another item. "
            "Please provide a link to the duplicated item in the comment."
        ),
    ] = "duplicate"
    other: Annotated[str, doc("Any other reason that doesn't fit the other report types")] = "other"

    @property
    def description(self) -> str:
        """Description to display in frontend"""
        desc: list[DocInfo] = [
            d for d in get_args(self.__annotations__[self.value]) if isinstance(d, DocInfo)
        ]
        if not desc:
            return ""
        return desc[0].documentation


_opened_by_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=True, index=True)
_resolved_by_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=True, index=True)
_target_account_id = Column(
    Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True, index=True
)


class Report(TableMixin, table=True):
    """Reports of items and accounts"""

    __tablename__ = "reports"

    report_id: IDField = Field(None, primary_key=True)
    report_type: ReportType
    opened_by_id: Optional[int] = Field(
        sa_column=_opened_by_id, description="The account that created this report"
    )
    opened_by: "Account" = Relationship(
        back_populates="opened_reports",
        sa_relationship=RelationshipProperty(
            "Account", foreign_keys=[_opened_by_id], back_populates="opened_reports"
        ),
    )
    resolved_by_id: Optional[int] = Field(
        sa_column=_resolved_by_id, description="The account that resolved this report"
    )
    resolved_by: "Account" = Relationship(
        back_populates="resolved_reports",
        sa_relationship=RelationshipProperty(
            "Account", foreign_keys=[_resolved_by_id], back_populates="resolved_reports"
        ),
    )
    comment: Optional[str] = Field(
        None, description="Additional information provided by the reporting account"
    )
    action: ModerationAction | None = Field(
        None, description="Action taken that resolved this report. None before action taken"
    )
    action_comment: Optional[str] = Field(
        None, description="Comment further explaining the resolution of the report"
    )

    target_dataset_id: Optional[int] = Field(
        default=None, foreign_key="datasets.dataset_id", ondelete="SET NULL", index=True
    )
    target_dataset: Optional["Dataset"] = Relationship(
        back_populates="reports", sa_relationship_kwargs={"lazy": "selectin"}
    )
    target_dataset_part_id: Optional[int] = Field(
        default=None, foreign_key="dataset_parts.dataset_part_id", ondelete="SET NULL", index=True
    )
    target_dataset_part: Optional["DatasetPart"] = Relationship(
        back_populates="reports", sa_relationship_kwargs={"lazy": "selectin"}
    )
    target_upload_id: Optional[int] = Field(
        default=None, foreign_key="uploads.upload_id", ondelete="SET NULL", index=True
    )
    target_upload: Optional["Upload"] = Relationship(
        back_populates="reports", sa_relationship_kwargs={"lazy": "selectin"}
    )
    target_account_id: Optional[int] = Field(sa_column=_target_account_id)
    target_account: Optional["Account"] = Relationship(
        back_populates="reports",
        sa_relationship=RelationshipProperty(
            "Account",
            foreign_keys=[_target_account_id],
            lazy="selectin",
            back_populates="reports",
        ),
    )

    @property
    def target(self) -> Union["Account", "Dataset", "DatasetPart", "Upload"]:
        target_fields = [f for f in type(self).model_fields if f.startswith("target_")]
        for field in target_fields:
            if tgt := getattr(self, field):
                return tgt
        raise ValueError(f"No target could be found for report, checked fields {target_fields}")


class ReportCreate(SQLModel):
    report_type: ReportType = Field(
        ...,
        schema_extra={"json_schema_extra": {"input_type": InputType.select}},
    )
    comment: Annotated[str, MaxLen(8192)] | None = Field(
        None,
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
    )
    target_type: TargetType
    target: str = Field(
        ...,
        description="""
        The identifier for the target type:\n
        - account: username            
        - dataset: slug
        - dataset_part: {dataset_slug}/{part_slug}
        - upload: infohash (v1 or v2)
        """,
    )

    def get_target(self, session: Session) -> TargetModels:
        return get_target(target_type=self.target_type, target=self.target, session=session)


class ReportRead(SQLModel):
    report_id: int
    report_type: ReportType
    comment: Annotated[str, MaxLen(8192)] | None = None
    target_type: TargetType
    target: TargetModelsRead
    opened_by: UsernameStr
    resolved_by: UsernameStr | None = None
    action: ModerationAction | None = None
    action_comment: str | None = None


def get_target(target_type: TargetType, target: str, session: Session) -> TargetModels:
    """
    target specified according to the target type:
    - account: username
    - dataset: slug
    - dataset_part: {dataset_slug}/{part_slug}
    - upload: infohash (v1 or v2)
    """
    from sciop import crud

    if target_type == "account":
        return crud.get_account(session=session, username=target)
    elif target_type == "dataset":
        return crud.get_dataset(session=session, dataset_slug=target)
    elif target_type == "dataset_part":
        try:
            ds_slug, part_slug = target.split("/")
        except ValueError as e:
            raise ValueError(
                f"Must pass dataset_part targets as {{dataset_slug}}/{{part_slug}}, "
                f"got {target}"
            ) from e
        return crud.get_dataset_part(
            session=session, dataset_slug=ds_slug, dataset_part_slug=part_slug
        )
    elif target_type == "upload":
        return crud.get_upload_from_infohash(session=session, infohash=target)
    else:
        raise ValueError(f"Unknown target type: {target_type}, must be one of {TargetType}")
