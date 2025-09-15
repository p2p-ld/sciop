from typing import Annotated, Any, Optional, TypeVar
from urllib.parse import parse_qsl, urlparse

import jwt
from fastapi import Body, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, ValidationError
from sciop.models.scope import AccountScopesRead
from sqlmodel import Session, select
from starlette.datastructures import QueryParams

from sciop import crud
from sciop.api.auth import ALGORITHM
from sciop.config import get_config
from sciop.db import iter_session
from sciop.models import (
    Account,
    AccountScopes,
    Dataset,
    DatasetClaim,
    DatasetPart,
    DatasetUpdate,
    ItemScopes,
    RaggedSearchParams,
    Report,
    SearchParams,
    Tag,
    TokenPayload,
    Upload,
)
from sciop.types import Scopes

_TModel = TypeVar("_TModel", bound=BaseModel)


class OAuth2PasswordBearerCookie(OAuth2PasswordBearer):
    """Password bearer that can also get a jwt from a cookie"""

    def __init__(self, cookie_key: str = "access_token", **kwargs: Any):
        self.cookie_key = cookie_key
        super().__init__(**kwargs)

    async def __call__(self, request: Request) -> Optional[str]:
        authorization = request.cookies.get(self.cookie_key)
        if not authorization:
            return await super().__call__(request)
        else:
            return authorization


reusable_oauth2 = OAuth2PasswordBearerCookie(
    cookie_key="access_token", tokenUrl=f"{get_config().api_prefix}/login", auto_error=False
)


def raw_session():
    """
    Get a session - put this in a wrapper function so it's invoked once per
    resolution of the dependency graph, rather than multiple times
    if one was just using `get_session` on its own
    """
    yield from iter_session()


RawSessionDep = Annotated[Session, Depends(raw_session)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def require_current_account(
    session: RawSessionDep, token: TokenDep, request: Request
) -> Account:
    if not token:
        raise HTTPException(401, detail="Not authorized", headers={"HX-Redirect": "/login"})

    try:
        payload = jwt.decode(
            token, get_config().secret_key.get_secret_value(), algorithms=[ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from e
    account = session.get(Account, token_data.sub)
    if not account:
        raise HTTPException(401, detail="Not authorized", headers={"HX-Redirect": "/login"})
    elif account.is_suspended:
        raise HTTPException(
            status_code=403, detail="Account is suspended", headers={"HX-Redirect": "/login"}
        )
    request.state.current_account = account
    return account


async def get_current_account(
    session: RawSessionDep, token: TokenDep, request: Request
) -> Optional[Account]:
    try:
        return await require_current_account(session, token, request)
    except HTTPException:
        return None


RequireCurrentAccount = Annotated[Account, Depends(require_current_account)]
CurrentAccount = Annotated[Optional[Account], Depends(get_current_account)]


async def get_accountable_session(
    session: RawSessionDep, account: CurrentAccount, request: Request
) -> Session:
    """Attach the current account to the session"""
    if account is not None:
        session.info["current_account_id"] = account.account_id
    return session


SessionDep = Annotated[Session, Depends(get_accountable_session)]


async def get_current_dataset(
    session: SessionDep, dataset_slug: Optional[str] = None
) -> Optional[Dataset]:
    if dataset_slug is None:
        return None
    dataset = crud.get_dataset(session=session, dataset_slug=dataset_slug)
    return dataset


def get_current_upload(session: SessionDep, infohash: Optional[str] = None) -> Optional[Upload]:
    if infohash is None:
        return None
    try:
        upload = crud.get_upload_from_infohash(session=session, infohash=infohash)
    except ValueError:
        # from e.g. if the infohash was just a random string or something
        return None
    return upload


CurrentDataset = Annotated[Optional[Dataset], Depends(get_current_dataset)]
CurrentUpload = Annotated[Optional[Upload], Depends(get_current_upload)]


def require_editable_item(dataset: CurrentDataset, upload: CurrentUpload) -> Dataset | Upload:
    """
    Gathering dependency to get one of a kind of editable item, depending on the url params present
    """
    if dataset is None and upload is None:
        raise HTTPException(404, detail="No editable item found")
    elif dataset is not None and upload is not None:
        raise HTTPException(500, detail="Ambiguous editable item")
    elif upload is not None:
        return upload
    elif dataset is not None:
        return dataset
    else:
        raise HTTPException(500, detail="Logically it should be impossible to be here!")


RequireEditableItem = Annotated[Dataset | Upload, Depends(require_editable_item)]


def require_current_active_root(current_account: RequireCurrentAccount) -> Account:
    if not current_account.has_scope("root"):
        raise HTTPException(status_code=403, detail="Account must be root")
    return current_account


def require_current_active_admin(current_account: RequireCurrentAccount) -> Account:
    if not current_account.has_scope("admin"):
        raise HTTPException(status_code=403, detail="Account must be admin")
    return current_account


def require_current_active_reviewer(current_account: RequireCurrentAccount) -> Account:
    if not current_account.has_scope("review"):
        raise HTTPException(status_code=403, detail="Account must be reviewer")
    return current_account


def require_current_active_uploader(current_account: RequireCurrentAccount) -> Account:
    if not current_account.has_scope("upload"):
        raise HTTPException(status_code=403, detail="Account must be uploader")
    return current_account


def require_current_editable_by(
    current_account: RequireCurrentAccount, editable: RequireEditableItem
) -> Account:
    if editable.editable_by(current_account):
        return current_account
    else:
        raise HTTPException(401, "Not permitted to edit")


RequireRoot = Annotated[Account, Depends(require_current_active_root)]
RequireAdmin = Annotated[Account, Depends(require_current_active_admin)]
RequireReviewer = Annotated[Account, Depends(require_current_active_reviewer)]
RequireUploader = Annotated[Account, Depends(require_current_active_uploader)]
RequireEditableBy = Annotated[Account, Depends(require_current_editable_by)]


def require_dataset(dataset: CurrentDataset, dataset_slug: str) -> Dataset:
    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"No such dataset {dataset_slug} exists!",
        )
    return dataset


def require_approved_dataset(dataset_slug: str, session: SessionDep) -> Dataset:
    """
    Require that a dataset exists and is is_approved
    """
    dataset = require_dataset(dataset_slug, session)
    if not dataset.is_approved:
        raise HTTPException(
            status_code=401,
            detail=f"Dataset {dataset_slug} not approved for uploads",
        )
    return dataset


RequireDataset = Annotated[Dataset, Depends(require_dataset)]
RequireApprovedDataset = Annotated[Dataset, Depends(require_approved_dataset)]


def require_visible_dataset(dataset: RequireDataset, current_account: CurrentAccount) -> Dataset:
    if dataset.visible_to(current_account):
        return dataset
    else:
        raise HTTPException(404)


RequireVisibleDataset = Annotated[Dataset, Depends(require_visible_dataset)]


def require_scopable_dataset(
    dataset: RequireVisibleDataset,
    current_account: RequireEditableBy,
    dataset_patch: Annotated[DatasetUpdate, Body()],
) -> Dataset:
    account_scopes = dataset_patch.account_scopes
    if not account_scopes or current_account.get_scope("review"):
        return dataset

    existing = {(scope.account.username, scope.scope.value) for scope in dataset.account_scopes}
    new = {(acct.username, scope) for acct in account_scopes for scope in acct.scopes if scope}
    changed = existing.symmetric_difference(new)

    if len(changed) == 0:
        return dataset

    if not current_account.get_scope("permissions", dataset_id=dataset.dataset_id):
        raise HTTPException(403, "You cannot modify permissions for this dataset.")

    if current_account.username in [scope[0] for scope in changed]:
        raise HTTPException(403, "You cannot modify your own permissions.")

    current_account_scopes = {e[1] for e in existing if e[0] == current_account.username}
    if len({scope[1] for scope in changed} - current_account_scopes.union({"edit"})):
        raise HTTPException(403, "You cannot modify permissions that you do not have.")

    return dataset


RequireScopableDataset = Annotated[Dataset, Depends(require_scopable_dataset)]


def current_dataset_part(
    dataset: RequireVisibleDataset, dataset_part_slug: str, session: SessionDep
) -> DatasetPart | None:
    part = crud.get_dataset_part(
        session=session, dataset_slug=dataset.slug, dataset_part_slug=dataset_part_slug
    )
    return part


def require_dataset_part(
    dataset_slug: str, dataset_part_slug: str, session: SessionDep
) -> DatasetPart:
    part = crud.get_dataset_part(
        session=session, dataset_slug=dataset_slug, dataset_part_slug=dataset_part_slug
    )
    if not part:
        raise HTTPException(
            status_code=404,
            detail=f"No such dataset part {dataset_slug}/{dataset_part_slug} exists!",
        )
    return part


CurrentDatasetPart = Annotated[DatasetPart | None, Depends(current_dataset_part)]
RequireDatasetPart = Annotated[DatasetPart, Depends(require_dataset_part)]


def require_visible_dataset_part(
    part: RequireDatasetPart, current_account: CurrentAccount
) -> DatasetPart:
    if part.visible_to(current_account):
        return part
    else:
        raise HTTPException(404)


RequireVisibleDatasetPart = Annotated[DatasetPart, Depends(require_visible_dataset_part)]


def require_upload(upload: CurrentUpload, infohash: str) -> Upload:
    if upload is None:
        raise HTTPException(
            status_code=404,
            detail=f"No such upload {infohash} exists!",
        )
    return upload


def require_approved_upload(infohash: str, session: SessionDep) -> Upload:
    upload = require_upload(infohash, session)
    if not upload.is_approved:
        raise HTTPException(
            status_code=401,
            detail=f"Upload {infohash} is not approved",
        )
    return upload


RequireUpload = Annotated[Upload, Depends(require_upload)]
RequireApprovedUpload = Annotated[Upload, Depends(require_approved_upload)]


def require_visible_upload(upload: RequireUpload, current_account: CurrentAccount) -> Upload:
    if upload.visible_to(current_account):
        return upload
    else:
        raise HTTPException(404)


RequireVisibleUpload = Annotated[Upload, Depends(require_visible_upload)]


def require_account(username: str, session: SessionDep) -> Account:
    """Require an existing, non-suspended account"""
    account = crud.get_account(session=session, username=username)
    if not account or account.is_suspended:
        raise HTTPException(
            status_code=404,
            detail=f"No such account {username} exists!",
        )
    return account


def require_any_account(username: str, session: SessionDep) -> Account:
    """Require any account, even if it is suspended"""
    account = crud.get_account(session=session, username=username)
    if not account:
        raise HTTPException(
            status_code=404,
            detail=f"No such account {username} exists!",
        )
    return account


RequireAccount = Annotated[Account, Depends(require_account)]
RequireAnyAccount = Annotated[Account, Depends(require_any_account)]


def require_tag(tag: str, session: SessionDep) -> Tag:
    existing_tag = crud.get_tag(session=session, tag=tag)
    if not existing_tag:
        raise HTTPException(
            status_code=404,
            detail=f"No such tag {tag} exists!",
        )
    return existing_tag


RequireTag = Annotated[Tag, Depends(require_tag)]


def valid_account_scope(scope_name: str | AccountScopes) -> Scopes:
    try:
        scope = getattr(AccountScopes, scope_name)
    except AttributeError:
        raise HTTPException(
            status_code=404,
            detail=f"No such scope as {scope_name} exists!",
        ) from None
    return scope


def valid_item_scope(scope_name: str | ItemScopes) -> Scopes:
    try:
        scope = getattr(ItemScopes, scope_name)
    except AttributeError:
        raise HTTPException(
            status_code=404,
            detail=f"No such scope as {scope_name} exists!",
        ) from None
    return scope


ValidAccountScope = Annotated[Scopes, Depends(valid_account_scope)]
ValidItemScope = Annotated[Scopes, Depends(valid_item_scope)]


def add_htmx_response_trigger(request: Request, response: Response) -> Response:
    """
    Add an htmx trigger to allow htmx elements to listen to a generic "response" event
    from other elements.

    e.g.:

        <div
          hx-get="/some/thing"
          hx-trigger="response from:.child"
        >
          <div>
            <span
              hx-get="/a/button/maybe"
              class=.child
            >
              assume this does something
            </span>
          </div>
        </div>
    """
    # yield response

    if "hx-request" in request.headers:
        if "hx-trigger" in response.headers:
            response.headers["hx-trigger"] = ",".join([response.headers["hx-trigger"], "response"])
        else:
            response.headers["hx-trigger"] = "response"
    return response


HTMXResponse = Annotated[Response, Depends(add_htmx_response_trigger)]


def parse_search_query_params(
    search: Annotated[SearchParams, Query()], request: Request
) -> SearchParams:
    """
    Parse searching and sorting params from query strings,
    """
    if "hx-current-url" in request.headers:
        current_params = parse_qsl(urlparse(request.headers["hx-current-url"]).query)
        query_params = QueryParams(current_params + request.query_params._list)
    else:
        query_params = request.query_params

    search_params = SearchParams.from_query_params(query_params)
    request.state.search_params = search_params
    return search_params


def parse_search_query_params_ignoring_current_url(
    search: Annotated[SearchParams, Query()], request: Request
) -> SearchParams:
    """
    Get search query params just from the current request, ignoring the current page url
    (e.g., for partials that don't affect the current url)

    Yeah it's a humongous function name, sue me.
    """
    search_params = SearchParams.from_query_params(request.query_params)
    request.state.search_params = search_params
    return search_params


def parse_ragged_query_params_ignoring_current_url(
    search: Annotated[RaggedSearchParams, Query()], request: Request
) -> SearchParams:
    """
    Like above, but using the ragged params model
    this is not DRY but there isn't an elegant way to change model fields here.
    """
    search_params = RaggedSearchParams.from_query_params(request.query_params)
    request.state.search_params = search_params
    return search_params


SearchQuery = Annotated[SearchParams, Depends(parse_search_query_params)]
SearchQueryNoCurrentUrl = Annotated[
    SearchParams, Depends(parse_search_query_params_ignoring_current_url)
]
RaggedQueryNoCurrentUrl = Annotated[
    RaggedSearchParams, Depends(parse_ragged_query_params_ignoring_current_url)
]


def current_dataset_claim(
    dataset: RequireVisibleDataset, current_account: RequireCurrentAccount, session: SessionDep
) -> DatasetClaim | None:
    stmt = select(DatasetClaim).where(
        DatasetClaim.dataset == dataset,
        DatasetClaim.dataset_part == None,  # noqa: E711
        DatasetClaim.account == current_account,
    )
    return session.exec(stmt).first()


def current_dataset_part_claim(
    dataset_part: RequireVisibleDatasetPart,
    current_account: RequireCurrentAccount,
    session: SessionDep,
) -> DatasetClaim | None:
    stmt = select(DatasetClaim).where(
        DatasetClaim.dataset_part == dataset_part, DatasetClaim.account == current_account
    )
    return session.exec(stmt).first()


CurrentDatasetClaim = Annotated[DatasetClaim | None, Depends(current_dataset_claim)]
CurrentDatasetPartClaim = Annotated[DatasetClaim | None, Depends(current_dataset_part_claim)]


def require_dataset_claim(claim: CurrentDatasetClaim) -> DatasetClaim:
    if claim is None:
        raise HTTPException(404)
    return claim


def require_dataset_part_claim(claim: CurrentDatasetPartClaim) -> DatasetClaim:
    if claim is None:
        raise HTTPException(404)
    return claim


RequireDatasetClaim = Annotated[DatasetClaim, Depends(require_dataset_claim)]
RequireDatasetPartClaim = Annotated[DatasetClaim, Depends(require_dataset_part_claim)]


def require_report(
    report_id: int, session: SessionDep, current_account: RequireCurrentAccount
) -> Report:
    """
    A report must exist and it must be visible to the current account
    """
    report = session.exec(select(Report).where(Report.report_id == report_id)).first()
    if report is None and current_account.has_scope("review"):
        # only show 404s to reviewers to hide the total number of reports
        raise HTTPException(404, "Report not found")
    elif report is None or not report.visible_to(current_account):
        raise HTTPException(403, "Not authorized to view report")
    return report


RequireReport = Annotated[Report, Depends(require_report)]
