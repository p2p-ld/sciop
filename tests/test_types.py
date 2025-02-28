import pytest

from sciop.models import ExternalIdentifierCreate


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
