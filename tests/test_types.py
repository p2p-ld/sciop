from datetime import UTC, datetime
from typing import Annotated, Optional

import pytest
from annotated_types import Le, MaxLen
from fastapi import HTTPException
from pydantic import BaseModel
from sqlmodel import select

from sciop.api.deps import check_scoped_limits
from sciop.models import Dataset, ExternalIdentifierCreate
from sciop.types import Scoped, Scopes


@pytest.mark.parametrize(
    "value",
    [
        "https://doi.org/10.23636/rcm4-zk44",
        "http://doi.org/10.23636/rcm4-zk44",
        "https://dx.doi.org/10.23636/rcm4-zk44",
        "http://dx.doi.org/10.23636/rcm4-zk44",
        "doi:10.23636/rcm4-zk44",
        "doi:/10.23636/rcm4-zk44",
    ],
)
def test_doi_normalisation(value):
    ext_id = ExternalIdentifierCreate(
        type="doi",
        identifier=value,
    )
    assert ext_id.identifier == "10.23636/rcm4-zk44"


def test_utc_datetime(dataset, session):
    """
    Test that UTCDatetime coerces datetime-naive objects to UTC without changing the hour value
    (for now we assume all input is in UTC, even though it probably isn't)
    """
    now_naive = datetime.today()
    assert now_naive.tzinfo is None
    _ = dataset(last_seen_at=now_naive)

    # after loading from db
    ds_loaded = session.exec(select(Dataset)).first()
    # need to revalidate to actually get utc timestamps after loading...
    ds_loaded = Dataset.model_validate(ds_loaded.model_dump())
    assert ds_loaded.last_seen_at.tzinfo is UTC
    assert ds_loaded.last_seen_at == now_naive.replace(tzinfo=UTC)


class _ScopedModel(BaseModel):
    items: Annotated[
        list[int],
        Scoped({Scopes.review: (), Scopes.upload: (MaxLen(3),), None: (MaxLen(1),)}),
    ] = []
    count: Annotated[Optional[int], Scoped({None: (Le(10),)})] = None


@pytest.mark.parametrize(
    "scopes,items,count,error_locs",
    [
        ([], [1], 10, []),
        ([], [1, 2], 11, [["body", "items"], ["body", "count"]]),
        ([Scopes.upload], [1, 2, 3], None, []),
        ([Scopes.upload], [1, 2, 3, 4], None, [["body", "items"]]),
        # the first scope the account has is used, so review lifts the upload limit
        ([Scopes.upload, Scopes.review], [1, 2, 3, 4], None, []),
        # fields without a scope that the account has fall back to the None limits
        ([Scopes.review], [1, 2, 3, 4], 11, [["body", "count"]]),
    ],
)
def test_scoped_limits(account, scopes, items, count, error_locs):
    """Scoped constraints are chosen by the account's scopes and collected per field"""
    model = _ScopedModel(items=items, count=count)
    acct = account(scopes=scopes, username="scoped")

    if not error_locs:
        check_scoped_limits(model, acct)
        return

    with pytest.raises(HTTPException) as e:
        check_scoped_limits(model, acct)
    assert e.value.status_code == 422
    assert [err["loc"] for err in e.value.detail] == error_locs
