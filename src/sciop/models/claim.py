from enum import StrEnum
from typing import Optional, Union

from pydantic import field_validator, model_validator
from sqlalchemy.schema import UniqueConstraint
from sqlmodel import Field, Relationship

from sciop.models.account import Account
from sciop.models.base import SQLModel
from sciop.models.dataset import Dataset, DatasetPart
from sciop.models.mixins import TableMixin
from sciop.types import IDField, SlugStr, UsernameStr, UTCDateTime


class ClaimStatus(StrEnum):
    in_progress = "in_progress"
    completed = "completed"


class DatasetClaimBase(SQLModel):
    status: ClaimStatus = Field(description="The current status of the dataset")


class DatasetClaim(DatasetClaimBase, TableMixin, table=True):
    __tablename__ = "dataset_claim"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "dataset_id",
            "dataset_part_id",
            name="_account_id_dataset_id_dataset_part_id_uc",
        ),
    )

    dataset_claim_id: IDField = Field(None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="datasets.dataset_id")
    dataset: Dataset = Relationship(back_populates="claims")
    dataset_part_id: Optional[int] = Field(
        default=None, foreign_key="dataset_parts.dataset_part_id"
    )
    dataset_part: Optional[DatasetPart] = Relationship(back_populates="claims")
    account_id: Optional[int] = Field(default=None, foreign_key="accounts.account_id")
    account: Account = Relationship(back_populates="claims")


class DatasetClaimRead(DatasetClaimBase, TableMixin):
    created_at: UTCDateTime
    updated_at: UTCDateTime
    dataset: SlugStr
    dataset_part: Optional[SlugStr] = Field(default=None)
    account: UsernameStr

    @model_validator(mode="before")
    @classmethod
    def orm_to_strings(cls, data: Union[dict, "DatasetClaim"]) -> dict:
        """Get slugs from dataset or dataset part"""
        if isinstance(data, DatasetClaim):
            dumped = data.model_dump(exclude_none=True)
            dumped["dataset"] = data.dataset.slug
            dumped["dataset_part"] = data.dataset_part.part_slug
            dumped["account"] = data.account.username
            return dumped
        return data

    @field_validator("account", mode="before")
    @classmethod
    def account_to_username(cls, value: Account | str) -> SlugStr:
        """Replace account object with username"""
        if not isinstance(value, str):
            value = value.username
        return value
