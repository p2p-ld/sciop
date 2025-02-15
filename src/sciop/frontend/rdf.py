from urllib.parse import urljoin

from fastapi import APIRouter, HTTPException
from starlette.requests import Request
from starlette.responses import Response
from rdflib.namespace import Namespace, RDF, RDFS, DCTERMS, DCAT, FOAF
from rdflib.graph import Graph
from rdflib.term import BNode, Literal, URIRef
from content_negotiation import decide_content_type, NoAgreeableContentTypeError

from sciop import crud
from sciop.api.deps import SessionDep
from sciop.config import config
from sciop.models.dataset import Dataset
from sciop.models.upload import Upload

DSID = Namespace(f"{config.public_url}/id/")
DSPG = Namespace(f"{config.public_url}/datasets/")

id_router = APIRouter(prefix="/id")
rdf_router = APIRouter(prefix="/rdf")


def serialise_graph(g: Graph, format: str) -> Response:
    if format == "ttl":
        return Response(g.serialize(format="ttl"), media_type="text/turtle")
    elif format == "rdf":
        return Response(g.serialize(format="xml"), media_type="application/rdf+xml")
    elif format == "nt":
        return Response(g.serialize(format="nt"), media_type="text/n-triples")
    elif format == "js":
        return Response(g.serialize(format="json-ld"), media_type="application/json")
    else:
        raise HTTPException(500, detail=f"Something went very wrong serializing an RDF graph")


def dataset_to_rdf(g: Graph, d: Dataset) -> Graph:
    g.add((DSID[d.slug], RDF["type"], DCAT["Dataset"]))
    g.add((DSID[d.slug], FOAF["isPrimaryTopicOf"], DSPG[d.slug]))
    g.add((DSID[d.slug], RDFS["label"], Literal(d.title)))
    g.add((DSID[d.slug], DCTERMS["title"], Literal(d.title)))
    g.add((DSID[d.slug], DCTERMS["publisher"], Literal(d.publisher)))
    if d.description is not None:
        g.add((DSID[d.slug], DCTERMS["description"], Literal(d.description)))
    if d.homepage is not None:
        g.add((DSID[d.slug], FOAF["homepage"], URIRef(d.homepage)))
    for tag in d.tags:
        g.add((DSID[d.slug], DCAT["keyword"], Literal(tag.tag)))
    for u in d.uploads:
        if not u.enabled:
            continue
        n = BNode()
        g.add((DSID[d.slug], DCAT["distribution"], n))
        g.add((n, RDF["type"], DCAT["Distribution"]))
        g.add((n, DCAT["downloadURL"], URIRef(u.absolute_download_path)))
        g.add((n, DCAT["mediaType"], Literal("application/x-bittorrent")))
    return g


@rdf_router.get("/datasets/{slug}.{suffix}")
async def dataset_graph(slug: str, suffix: str, session: SessionDep) -> Response:
    if suffix not in suffix_to_ctype:
        raise HTTPException(404, detail=f"No such serialisation: {suffix}")
    d = crud.get_dataset(session=session, dataset_slug=slug)
    if d is None or not d.enabled:
        raise HTTPExcception(404, detail=f"No such dataset: {slug}")
    g = Graph()
    dataset_to_rdf(g, d)
    return serialise_graph(g, suffix)


@rdf_router.get("/tag/{tag}.{suffix}")
async def tag_feed(tag: str, suffix: str, session: SessionDep) -> Response:
    if suffix not in suffix_to_ctype:
        raise HTTPException(404, detail=f"No such serialisation: {suffix}")
    datasets = crud.get_approved_datasets_from_tag(session=session, tag=tag)
    if not datasets:
        raise HTTPException(404, detail=f"No datasets found for tag {tag}")
    g = Graph()
    cat = URIRef(f"{config.public_url}/tag/{tag}")
    g.add((cat, RDF["type"], DCAT["Catalog"]))
    g.add((cat, RDFS["label"], Literal(f"SciOp catalog for tag: {tag}")))
    g.add((cat, DCTERMS["title"], Literal(f"SciOp catalog for tag: {tag}")))

    for d in datasets:
        g.add((cat, DCAT["dataset"], DSID[d.slug]))
        dataset_to_rdf(g, d)

    return serialise_graph(g, suffix)


## Content-type autonegotiation plumbing
suffix_to_ctype = {
    "ttl": "text/turtle",
    "rdf": "application/rdf+xml",
    "nt": "text/n-triples",
    "js": "application/json",
}
ctype_to_suffix = {v: k for k, v in suffix_to_ctype.items()}


@id_router.get("/{slug}")
async def id_redirect(slug: str, request: Request) -> Response:
    try:
        content_type = decide_content_type(
            request.headers.get("accept", "text/html").split(","),
            ["text/html", "application/xhtml+xml"],
        )
        return Response(status_code=303, headers={"Location": f"/datasets/{slug}"})
    except NoAgreeableContentTypeError:
        return Response(status_code=303, headers={"Location": f"/rdf/datasets/{slug}"})


@rdf_router.get("/datasets/{slug}")
async def dataset_autoneg(
    slug: str, session: SessionDep, request: Request, response: Response
) -> Response:
    try:
        content_type = decide_content_type(
            request.headers.get("accept", "text/turtle").split(","), list(ctype_to_suffix)
        )
        suffix = ctype_to_suffix[content_type]
        return Response(status_code=303, headers={"Location": f"{slug}.{suffix}"})
    except NoAgreeableContentTypeError:
        raise HTTPException(406, detail="No suitable serialisation, sorry")


@rdf_router.get("/tag/{tag}")
async def tag_autoneg(
    tag: str, session: SessionDep, request: Request, response: Response
) -> Response:
    try:
        content_type = decide_content_type(
            request.headers.get("accept", "text/turtle").split(","), list(ctype_to_suffix)
        )
        suffix = ctype_to_suffix[content_type]
        return Response(status_code=303, headers={"Location": f"{tag}.{suffix}"})
    except NoAgreeableContentTypeError:
        raise HTTPException(406, detail="No suitable serialisation, sorry")
