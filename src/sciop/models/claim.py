"""
Models for coordinating automated dispersed scraping using dataset parts and
[`sciop-scraping`](https://codeberg.org/Safeguarding/sciop-scraping)

Powering the sciopteam swarrior, aka: The Kronkelianator 2.
"""

from enum import StrEnum
from typing import Optional, Union

from pydantic import model_validator
from sqlalchemy.schema import UniqueConstraint
from sqlmodel import Field, Relationship

from sciop.models.account import Account
from sciop.models.base import SQLModel
from sciop.models.dataset import Dataset, DatasetPart
from sciop.models.mixins import TableMixin
from sciop.types import IDField, SlugStr, UsernameStr, UTCDateTime


class ClaimStatus(StrEnum):
    """
    An initial claim is made with in_progress,
    then marked as completed after the scrape is finished.
    When the upload is made the claim is removed.
    """

    in_progress = "in_progress"
    """The account has indicated that it is currently scraping the item"""
    completed = "completed"
    """The account has finished scraping the item, but has not yet uploaded a torrent for it"""


class DatasetClaimBase(SQLModel):
    """Fields shared by all models in the DatasetClaim family"""

    status: ClaimStatus = Field(description="The current status of the dataset")


class DatasetClaim(DatasetClaimBase, TableMixin, table=True):
    """
    ORM model for DatasetClaim

    A DatasetClaim is always associated with a [`Dataset`][sciop.models.Dataset],
    and optionally with a [`DatasetPart`][sciop.models.DatasetPart].
    (The presence of a Dataset is thus not distinguishing between
    a claim on a Dataset and one of its parts,
    and one needs to check if `dataset_part` is `None`)

    This ends up saving us a tiny bit of time not needing to join to find the dataset.

    Each [account][sciop.models.Account] can only have one claim per dataset or dataset part.
    """

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
    """
    Version of DatasetClaim used when returning from the API or displaying publicly.

    `*Read` models are used to transform values from their database representation to an
    externally useful one (e.g. substituting the entire [`Dataset`][sciop.models.Dataset]
    model for its slug), as well as remove any internal fields, etc.
    """

    created_at: UTCDateTime
    updated_at: UTCDateTime
    dataset: SlugStr
    dataset_part: Optional[SlugStr] = Field(default=None)
    account: UsernameStr

    @model_validator(mode="before")
    @classmethod
    def orm_to_strings(cls, data: Union[dict, "DatasetClaim"]) -> dict:
        """
        Convert ORM models to their string shorthands

        - `dataset` to [slug][sciop.models.Dataset.slug]
        - `dataset_part` to its [part_slug][sciop.models.DatasetPart.part_slug]
        - `account` to [username][sciop.models.Account.username]
        """
        if isinstance(data, DatasetClaim):
            dumped = data.model_dump(exclude_none=True)
            dumped["dataset"] = data.dataset.slug
            dumped["dataset_part"] = data.dataset_part.part_slug
            dumped["account"] = data.account.username
            return dumped
        return data
