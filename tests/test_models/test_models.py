"""
Tests generic across models
"""

import pytest
from sqlmodel.main import FieldInfo

from sciop import models

TABLE_MODELS = (
    getattr(models, m) for m in models.__all__ if hasattr(getattr(models, m), "__table__")
)


@pytest.mark.parametrize("model", TABLE_MODELS)
def test_fields_are_sqlmodel_field(model):
    """
    When a pydantic field has extra types,
    they get shoved into `json_schema_extra`.
    This breaks sqlmodel Field params, so all ``Field`` objects must be sqlmodel,
    not pydantic ``Field`` types, when they have extra values,
     or else weird and bad things happen
    """
    for k, v in model.model_fields.items():
        if isinstance(v, FieldInfo):
            continue
        assert not v.json_schema_extra, f"field {k} must be sqlmodel field if it has extra params"
