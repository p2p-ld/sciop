"""
These tests are just for our functions that handle migrations,
the actual migrations themselves are tested by pytest-alembic
https://pytest-alembic.readthedocs.io/
and imported here
"""

# ruff: noqa: F401

from pytest_alembic.tests import (
    test_model_definitions_match_ddl,
    test_single_head_revision,
    test_up_down_consistency,
    test_upgrade,
)
