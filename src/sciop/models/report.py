from datetime import UTC, datetime
from enum import StrEnum
from typing import (
    TYPE_CHECKING,
    Annotated,
    Literal,
    Optional,
    Self,
    TypeAlias,
    Union,
    get_args,
)

import sqlalchemy as sqla
from annotated_types import DocInfo, MaxLen, doc
from pydantic import BaseModel
from sqlalchemy import Column, ColumnElement, ForeignKey, Integer
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import RelationshipProperty
from sqlmodel import Field, Relationship, Session, select

from sciop.exceptions import (
    InvalidModerationActionError,
    ModerationPermissionsError,
    ReportResolvedError,
)
from sciop.models.base import SQLModel
from sciop.models.mixins import FrontendMixin, SortableCol, SortMixin, TableMixin
from sciop.models.moderation import ReportAction
from sciop.types import IDField, InputType, UsernameStr, UTCDateTime

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


class ReportBase(SQLModel, FrontendMixin):
    report_id: IDField

    @property
    def frontend_url(self) -> str:
        return f"/reports/{self.report_id}"

    @property
    def short_name(self) -> str:
        return str(self.report_id)


class Report(ReportBase, TableMixin, SortMixin, table=True):
    """Reports of items and accounts"""

    __name__ = "report"
    __tablename__ = "reports"
    __sortable__ = (
        SortableCol(name="report_id", title="ID"),
        SortableCol(name="opened_by", title="By"),
        SortableCol(name="report_type", title="Type"),
        SortableCol(name="target_type", title="Target"),
        SortableCol(name="report_name", title="Name"),
        SortableCol(name="created_at", title="Opened"),
    )

    report_id: IDField = Field(None, primary_key=True)
    report_type: ReportType
    opened_by_id: Optional[int] = Field(
        None, sa_column=_opened_by_id, description="The account that created this report"
    )
    opened_by: "Account" = Relationship(
        back_populates="opened_reports",
        sa_relationship=RelationshipProperty(
            "Account", foreign_keys=[_opened_by_id], back_populates="opened_reports"
        ),
    )
    resolved_by_id: Optional[int] = Field(
        None, sa_column=_resolved_by_id, description="The account that resolved this report"
    )
    resolved_by: "Account" = Relationship(
        back_populates="resolved_reports",
        sa_relationship=RelationshipProperty(
            "Account", foreign_keys=[_resolved_by_id], back_populates="resolved_reports"
        ),
    )
    resolved_at: Optional[UTCDateTime] = Field(
        None, description="The UTC time when the report was resolved"
    )
    comment: Optional[str] = Field(
        None, description="Additional information provided by the reporting account"
    )
    action: ReportAction | None = Field(
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
    target_account_id: Optional[int] = Field(None, sa_column=_target_account_id)
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
        target_fields = [
            f for f in type(self).__sqlmodel_relationships__ if f.startswith("target_")
        ]
        for field in target_fields:
            if tgt := getattr(self, field):
                return tgt
        raise ValueError(f"No target could be found for report, checked fields {target_fields}")

    @property
    def target_type(self) -> TargetType:
        from sciop.models import (
            Account,
            Dataset,
            DatasetPart,
            Upload,
        )

        tgt = self.target
        if isinstance(tgt, Account):
            return "account"
        elif isinstance(tgt, Dataset):
            return "dataset"
        elif isinstance(tgt, DatasetPart):
            return "dataset_part"
        elif isinstance(tgt, Upload):
            return "upload"
        else:
            raise ValueError(f"Unknown target type for target {tgt}")

    @hybrid_property
    def target_name(self) -> str:
        return self.target.short_name

    @target_name.inplace.expression
    @classmethod
    def _target_name(cls) -> ColumnElement[str]:
        from sciop.models import Account, Dataset, DatasetPart, Upload

        # don't @ me about this heinously verbose shit
        q = sqla.case(
            (
                cls.target_account_id != None,  # noqa: E711
                (
                    select(Account.short_name)
                    .join(Account.reports)
                    .where(Account.account_id == cls.target_account_id)
                    .scalar_subquery()
                ),
            ),
            (
                cls.target_dataset_id != None,  # noqa: E711
                (
                    select(Dataset.short_name)
                    .join(Dataset.reports)
                    .where(Dataset.dataset_id == cls.target_dataset_id)
                    .scalar_subquery()
                ),
            ),
            (
                cls.target_dataset_part_id != None,  # noqa: E711
                (
                    select(DatasetPart.short_name)
                    .join(DatasetPart.reports)
                    .where(DatasetPart.dataset_part_id == cls.target_dataset_part_id)
                    .scalar_subquery()
                ),
            ),
            (
                cls.target_upload_id != None,  # noqa: E711
                (
                    select(Upload.short_name)
                    .join(Upload.reports)
                    .where(Upload.upload_id == cls.target_upload_id)
                    .scalar_subquery()
                ),
            ),
        ).label("target_name")
        return q

    @hybrid_method
    def visible_to(self, account: Optional["Account"] = None) -> bool:
        """Reports are visible to moderators and the account that made the report"""
        if account is None:
            return False
        return self.opened_by == account or account.has_scope("review")

    @visible_to.inplace.expression
    @classmethod
    def _visible_to(cls, account: Optional["Account"] = None) -> ColumnElement[bool]:
        if account is None:
            return sqla.false()

        return sqla.or_(cls.opened_by == account, account.has_scope("review") == True)

    @property
    def reported_account(self) -> "Account":
        """
        The report target if the report directly reports the account,
        otherwise the account that owns the reported item
        """
        if self.target_type == "account":
            return self.target
        else:
            return self.target.account

    @hybrid_property
    def is_open(self) -> bool:
        """
        A report is open if it has not been resolved,
        ie. it does not have an action taken against it.
        """
        # equality comparison to None is valid with sqlalchemy
        return self.action == None  # noqa: E711

    def resolve(
        self, action: "ReportResolve", resolved_by: "Account", session: Session
    ) -> "Report":
        """
        Resolve the report, taking the requested action.
        This assumes that the account has already been validated as able to resolve the report.

        See :class:`.ReportAction` for description of actions

        Raises:
            ReportResolvedError if the report has already been resolved
        """
        if self.action:
            raise ReportResolvedError(
                f"Report {self.report_id} has already been resolved with {self.action} "
                f"by {self.resolved_by.username} on {self.resolved_at.isoformat()}"
            )
        elif self.report_id != action.report_id:
            raise InvalidModerationActionError(
                f"Attempted to resolve report {action.report_id} on report {self.report_id}"
            )
        elif (
            self.reported_account
            and self.reported_account.account_id == resolved_by.account_id
            and not resolved_by.has_scope("root")
        ):
            raise ModerationPermissionsError("Can't resolve reports about yourself")

        if action.action == ReportAction.dismiss:
            # do nothing
            pass
        elif action.action == ReportAction.hide:
            if self.target_type == "account":
                raise InvalidModerationActionError("Accounts can't be hidden")
            self.target.hide(account=resolved_by, session=session)
        elif action.action == ReportAction.remove:
            if self.target_type == "account":
                raise InvalidModerationActionError("Accounts can't be removed (use suspend)")
            self.target.remove(account=resolved_by, session=session)
        elif action.action == ReportAction.suspend:
            if self.target_type == "account":
                self.target.suspend(suspended_by=resolved_by, session=session)
            else:
                self.target.account.suspend(suspended_by=resolved_by, session=session)
        elif action.action == ReportAction.suspend_remove:
            account = self.target if self.target_type == "account" else self.target.account
            # check first before removing items if we're allowed to do this
            if not resolved_by.can_suspend(account):
                raise ModerationPermissionsError(
                    f"Not permitted to suspend and remove items from {account.username}"
                )
            account.remove_items(removed_by=resolved_by, session=session)
        else:
            raise InvalidModerationActionError(f"Invalid report resolution action {action.action}")

        self.resolved_by = resolved_by
        self.resolved_at = datetime.now(UTC)
        self.action = action.action
        self.action_comment = action.action_comment
        session.add(self)
        session.commit()
        return self

    def action_valid(self, action: "ReportAction", current_account: "Account") -> bool:
        """
        Check if a given action is valid for the report,
        given its type and the account trying to take the action.

        Intended for use in the frontend to filter displayed action buttons,
        not to control the ability to take an action -
        that is controlled by the `resolve` method,
        which raises more informative error messages.
        """
        if not current_account.has_scope("review"):
            return False
        if (
            self.reported_account
            and self.reported_account.username == current_account.username
            and not current_account.has_scope("root")
        ):
            return False

        if action == ReportAction.dismiss:
            return True
        elif action == ReportAction.hide or action == ReportAction.remove:
            return self.target_type != "account"
        elif action in (ReportAction.suspend, ReportAction.suspend_remove):
            return current_account.has_scope("admin")


class ReportCreate(SQLModel):
    report_type: ReportType = Field(
        ...,
        schema_extra={"json_schema_extra": {"input_type": InputType.select}},
    )
    comment: str | None = Field(
        None,
        max_length=8192,
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
        description="Please provide an explanation for your report, "
        "including any details or context that would help moderators evaluate it.",
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


class ReportResolve(BaseModel):
    report_id: int
    action: ReportAction
    action_comment: Optional[str] = None


class ReportRead(ReportBase):
    report_id: int
    created_at: UTCDateTime
    report_type: ReportType
    comment: Annotated[str, MaxLen(8192)] | None = None
    target_type: TargetType
    target_name: str
    target: TargetModelsRead
    opened_by: UsernameStr
    resolved_by: UsernameStr | None = None
    action: ReportAction | None = None
    action_comment: str | None = None

    @property
    def is_open(self) -> bool:
        return self.action is None

    @classmethod
    def from_report(cls, report: Report) -> Self:
        return ReportRead.model_validate(
            report, update={"target_type": report.target_type, "target": report.target.to_read()}
        )


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
