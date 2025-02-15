from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from sciop.frontend.templates import templates

test_router = APIRouter(prefix="/test")


@test_router.get("/", response_class=HTMLResponse, include_in_schema=False)
def test(request: Request):
    return templates.TemplateResponse("pages/test.html", {"request": request})


@test_router.post("/500")
def raise_500(request: Request):
    raise HTTPException(500, detail="This is just a 500!")
