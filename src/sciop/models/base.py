from pydantic import ConfigDict
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlmodel import SQLModel as _SQLModel


class SQLModel(_SQLModel):
    """Base model to hold configuration for all models"""

    model_config = ConfigDict(use_enum_values=True, ignored_types=(hybrid_method, hybrid_property))
