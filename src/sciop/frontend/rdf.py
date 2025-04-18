from typing import Dict, Tuple

from content_negotiation import NoAgreeableContentTypeError, decide_content_type
from fastapi import APIRouter, HTTPException
from rdflib.graph import Graph as RGraph
from rdflib.namespace import DCAT, DCTERMS, FOAF, RDF, RDFS, Namespace
from rdflib.term import BNode, Literal, URIRef
from starlette.requests import Request
from starlette.responses import Response

from sciop import crud
from sciop.api.deps import SessionDep
from sciop.config import config
from sciop.models.dataset import Dataset
from sciop.types import ctype_to_suffix, suffix_to_ctype

BIBO = Namespace("http://purl.org/ontology/bibo/")
TAGS = Namespace(f"{config.base_url}/id/tag/")
DSID = Namespace(f"{config.base_url}/id/datasets/")
DSPG = Namespace(f"{config.base_url}/datasets/")
SCIOP = Namespace("https://sciop.net/ns#")

rdf_router = APIRouter(prefix="/rdf")


class Graph(RGraph):
    """
    A helper Graph class that registers our prefixes
    for nicer serialisations
    """

    def __init__(self, *av: Tuple, **kw: Dict) -> None:
        super().__init__(*av, **kw)
        self.namespace_manager.bind("bibo", BIBO)
        self.namespace_manager.bind("tags", TAGS)
        self.namespace_manager.bind("dset", DSID)
        self.namespace_manager.bind("sciop", SCIOP)


def serialise_graph(g: Graph, format: str) -> Response:
    """
    Serialises an RDF graph into an HTTP response, setting
    the content-type header correctly.
    """
    if format == "ttl":
        return Response(g.serialize(format="ttl"), media_type=suffix_to_ctype[format])
    elif format == "rdf":
        return Response(g.serialize(format="xml"), media_type=suffix_to_ctype[format])
    elif format == "nt":
        return Response(g.serialize(format="nt"), media_type=suffix_to_ctype[format])
    elif format == "json":
        return Response(g.serialize(format="json-ld"), media_type=suffix_to_ctype[format])
    else:
        raise HTTPException(500, detail="Something went very wrong serializing an RDF graph")


def dataset_to_rdf(g: Graph, d: Dataset) -> Graph:
    """
    Populate the graph with a description of the dataset using
    the DCAT vocabulary. This might be better on the dataset.
    """
    g.add((DSID[d.slug], RDF["type"], DCAT["Dataset"]))
    g.add((DSID[d.slug], FOAF["isPrimaryTopicOf"], DSPG[d.slug]))
    g.add((DSID[d.slug], RDFS["label"], Literal(d.title)))
    g.add((DSID[d.slug], DCTERMS["title"], Literal(d.title)))
    g.add((DSID[d.slug], DCTERMS["publisher"], Literal(d.publisher)))
    if d.description is not None:
        g.add((DSID[d.slug], DCTERMS["description"], Literal(d.description)))
    if d.homepage is not None:
        g.add((DSID[d.slug], FOAF["homepage"], URIRef(d.homepage)))
    if d.dataset_created_at is not None:
        g.add((DSID[d.slug], DCTERMS["created"], Literal(d.dataset_created_at)))
    if d.dataset_updated_at is not None:
        g.add((DSID[d.slug], DCTERMS["modified"], Literal(d.dataset_updated_at)))
    for tag in d.tags:
        g.add((DSID[d.slug], DCAT["keyword"], Literal(tag.tag)))
        g.add((DSID[d.slug], DCAT["inCatalog"], TAGS[tag.tag]))
    for u in d.urls:
        n = BNode()
        g.add((DSID[d.slug], DCAT["distribution"], n))
        g.add((n, RDF["type"], DCAT["Distribution"]))
        g.add((n, DCAT["downloadURL"], URIRef(u.url)))
    for i in d.external_identifiers:
        g.add((DSID[d.slug], DCTERMS["identifier"], Literal(i.identifier)))
        if i.uri is not None:
            g.add((DSID[d.slug], SCIOP[i.type], URIRef(i.uri)))
        if i.type in ("doi", "isbn", "issn"):
            g.add((DSID[d.slug], BIBO[i.type], Literal(i.identifier)))
    for u in d.uploads:
        if not u.is_visible:
            continue
        n = BNode()
        g.add((DSID[d.slug], DCAT["distribution"], n))
        g.add((n, RDF["type"], DCAT["Distribution"]))
        g.add((n, DCAT["downloadURL"], URIRef(u.absolute_download_path)))
        g.add((n, DCAT["mediaType"], Literal("application/x-bittorrent")))
    for s in d.external_sources:
        n = BNode()
        g.add((DSID[d.slug], DCTERMS["contributor"], n))
        if s.name is not None:
            g.add((n, FOAF["name"], Literal(s.source)))
        if s.url is not None:
            g.add((n, FOAF["homepage"], URIRef(s.url)))
        if s.description is not None:
            g.add((n, DCTERMS["description"], Literal(s.description)))
    docs = [
        URIRef(f"{config.base_url}/rdf/datasets/{d.slug}.ttl"),
        URIRef(f"{config.base_url}/rdf/datasets/{d.slug}.rdf"),
        URIRef(f"{config.base_url}/rdf/datasets/{d.slug}.json"),
        URIRef(f"{config.base_url}/rdf/datasets/{d.slug}.nt"),
    ]
    for doc in docs:
        g.add((DSID[d.slug], FOAF["isPrimaryTopicOf"], doc))
    return g


@rdf_router.get("/datasets/{slug}.{suffix}")
async def dataset_graph(slug: str, suffix: str, session: SessionDep) -> Response:
    """
    Produce a dcat:Dataset from a dataset.
    """
    if suffix not in suffix_to_ctype:
        raise HTTPException(404, detail=f"No such serialisation: {suffix}")
    d = crud.get_dataset(session=session, dataset_slug=slug)
    if d is None or not d.is_visible:
        raise HTTPException(404, detail=f"No such dataset: {slug}")
    g = Graph()
    dataset_to_rdf(g, d)
    return serialise_graph(g, suffix)


@rdf_router.get("/tag/{tag}.{suffix}")
async def tag_graph(tag: str, suffix: str, session: SessionDep) -> Response:
    """
    Produce a dcat:Catalog from a tag. A catalog contains several datasets.
    """
    if suffix not in suffix_to_ctype:
        raise HTTPException(404, detail=f"No such serialisation: {suffix}")
    datasets = crud.get_visible_datasets_from_tag(session=session, tag=tag)
    if not datasets:
        raise HTTPException(404, detail=f"No datasets found for tag {tag}")
    g = Graph()
    cat = TAGS[tag]
    g.add((cat, RDF["type"], DCAT["Catalog"]))
    g.add((cat, RDFS["label"], Literal(f"SciOp catalog for tag: {tag}")))
    g.add((cat, DCTERMS["title"], Literal(f"SciOp catalog for tag: {tag}")))
    docs = [
        URIRef(f"{config.base_url}/rdf/tag/{tag}.ttl"),
        URIRef(f"{config.base_url}/rdf/tag/{tag}.rdf"),
        URIRef(f"{config.base_url}/rdf/tag/{tag}.nt"),
        URIRef(f"{config.base_url}/rdf/tag/{tag}.json"),
        URIRef(f"{config.base_url}/rdf/tag/{tag}.rss"),
    ]
    for doc in docs:
        g.add((cat, FOAF["isPrimaryTopicOf"], doc))

    for d in datasets:
        g.add((cat, DCAT["dataset"], DSID[d.slug]))
        dataset_to_rdf(g, d)

    return serialise_graph(g, suffix)


## Content-type autonegotiation plumbing

id_router = APIRouter(prefix="/id")


@id_router.get("/{entity}/{ident}")
def autoneg(entity: str, ident: str, session: SessionDep, request: Request) -> Response:
    """
    Automatically negotiate content-type for requests under the /id namespace

    This understands several flavours of RDF, HTML, and RSS.

    Requesting /id/tag/foo will yield a redirect to:

    - /tag/foo if an HTML page is requested
    - /rss/tag/foo.rss if an RSS feed is requested
    - /rdf/tag/foo.ttl if Turtle is requested

    And similarly for /id/datasets/bar

    This means that we can construct a canonical (for us) identifier for datasets
    and tags using the {config.base_url}/id/ prefix.
    """
    try:
        content_type = decide_content_type(
            request.headers.get("accept", "text/html").split(","), list(ctype_to_suffix)
        )
        suffix = ctype_to_suffix[content_type]
        if suffix in ["html", "xhtml"]:
            return Response(status_code=303, headers={"Location": f"/{entity}/{ident}"})
        elif suffix == "rss":
            return Response(status_code=303, headers={"Location": f"/rss/{entity}/{ident}.rss"})
        else:
            return Response(
                status_code=303, headers={"Location": f"/rdf/{entity}/{ident}.{suffix}"}
            )
    except NoAgreeableContentTypeError:
        raise HTTPException(406, detail="No suitable serialisation, sorry") from None
