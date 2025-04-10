from pydantic import ConfigDict
from sqlmodel import SQLModel as _SQLModel


class SQLModel(_SQLModel):
    """Base model to hold configuration for all models"""

    model_config = ConfigDict(use_enum_values=True)
