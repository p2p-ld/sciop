import pytest
import rdflib

from sciop.types import suffix_to_ctype

LD_SUFFIXES = ("ttl", "rdf", "nt", "json")


@pytest.mark.parametrize("suffix", LD_SUFFIXES)
def test_url_escaped(suffix, upload, torrentfile, dataset, client):
    """
    URLs with spaces don't break RDF feeds
    """
    t = torrentfile(file_name="torrent with spaces.torrent")
    ds = dataset(tags=["test"])
    ul = upload(torrentfile_=t, dataset_=ds)
    res = client.get(f"/rdf/tag/test.{suffix}")
    assert res.status_code == 200

    g = rdflib.Graph()
    g.parse(data=res.text, format=suffix_to_ctype[suffix])
    trips = list(g.triples((None, rdflib.namespace.DCAT.downloadURL, None)))
    objs = [str(t[2]) for t in trips]
    assert any(["torrent%20with%20spaces.torrent" in o for o in objs])
