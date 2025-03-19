from datetime import UTC, datetime

import pytest
from sqlmodel import select

from sciop.models import Dataset, ExternalIdentifierCreate


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
    ds_loaded = Dataset.model_validate(ds_loaded)
    assert ds_loaded.last_seen_at.tzinfo is UTC
    assert ds_loaded.last_seen_at == now_naive.replace(tzinfo=UTC)
