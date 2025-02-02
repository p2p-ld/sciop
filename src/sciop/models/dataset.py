from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING, List, Literal
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field, Relationship

from sciop.models.account import Account


class Priority(str, Enum):
    unknown = "unknown"
    low = "low"
    medium = "medium"
    high = "high"

class SourceType(str, Enum):
    http = "web"
    ftp = "ftp"
    s3 = "s3"

class Status(str, Enum):
    todo = "todo"
    claimed = "claimed"
    completed = "completed"


class DatasetBase(SQLModel):
    agency: str
    """Agency or organization"""
    slug: str
    """Short, computer readable name for dataset"""
    title: str
    """Human readable name for dataset"""
    priority: Priority = "unknown"
    source: SourceType
    status: Status = "todo"




class Dataset(DatasetBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    instances: list["DatasetInstance"] = Relationship(back_populates="dataset")
    url: list["DatasetURL"] = Relationship(back_populates="dataset")
    tags: list["DatasetTag"] = Relationship(back_populates="dataset")

class DatasetURL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    dataset: Dataset = Relationship(back_populates="url")
    url: str

class DatasetTag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    dataset: Dataset = Relationship(back_populates="url")
    tag: str



class DatasetInstanceBase(SQLModel):
    """
    A copy of a dataset
    """
    time_submitted: datetime = Field(default_factory=lambda: datetime.now(UTC))
    method: str
    """Description of how the dataset was acquired"""




class DatasetInstance(DatasetInstanceBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    dataset: Dataset = Relationship(back_populates="instances")
    submitted_by: Account = Relationship(back_populates="submissions")



