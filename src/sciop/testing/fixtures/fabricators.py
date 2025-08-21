import hashlib
import random
import string
from collections.abc import Callable as C
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Concatenate, Optional
from typing import Literal as L

import numpy as np
import pytest
from sqlmodel import Session
from torrent_models import Torrent

from sciop.models import (
    Account,
    Dataset,
    Token,
    TorrentFile,
    Upload,
)
from sciop.testing.fabricators import (
    P,
    default_torrent,
    fake,
    make_account,
    make_dataset,
    make_torrent,
    make_torrentfile,
    make_upload,
)
from sciop.types import Scopes

__all__ = [
    "account",
    "account_module",
    "admin_auth_header",
    "admin_user",
    "admin_token",
    "dataset",
    "dataset_module",
    "default_db",
    "get_auth_header",
    "infohashes",
    "reviewer",
    "root_auth_header",
    "root_user",
    "root_token",
    "torrent",
    "torrent_module",
    "torrent_pair",
    "torrentfile",
    "torrentfile_module",
    "upload",
    "upload_module",
    "uploader",
]


@pytest.fixture
def infohashes() -> C[[], dict[L["v1_infohash", "v2_infohash"], str]]:
    """Fixture function to generate "unique" infohashes"""

    def _infohashes() -> dict[L["v1_infohash", "v2_infohash"], str]:
        files = [
            {
                "path": fake.file_name(),
                "size": np.random.default_rng().integers(16 * (2**10), 32 * (2**10)),
            }
            for i in range(5)
        ]
        hash_data = "".join([str(f) for f in files])
        hash_data = hash_data.encode("utf-8")
        return {
            "v1_infohash": hashlib.sha1(hash_data).hexdigest(),
            "v2_infohash": hashlib.sha256(hash_data).hexdigest(),
        }

    return _infohashes


@pytest.fixture
def account(
    session: Session,
) -> C[Concatenate[list[Scopes] | None, bool, Session | None, bool, P], "Account"]:
    def _account_inner(
        scopes: list[Scopes] = None,
        is_suspended: bool = False,
        session_: Session | None = None,
        create_only: bool = False,
        **kwargs: P.kwargs,
    ) -> Account:
        if not session_:
            session_ = session
        return make_account(
            scopes=scopes,
            is_suspended=is_suspended,
            session_=session_,
            create_only=create_only,
            **kwargs,
        )

    return _account_inner


@pytest.fixture(scope="module")
def account_module(
    session_module: Session,
) -> C[Concatenate[list[Scopes] | None, bool, Session | None, bool, P], "Account"]:
    def _account_inner(
        scopes: list[Scopes] = None,
        is_suspended: bool = False,
        session_: Session | None = None,
        create_only: bool = False,
        **kwargs: P.kwargs,
    ) -> Account:
        if not session_:
            session_ = session_module
        return make_account(
            scopes=scopes,
            is_suspended=is_suspended,
            session_=session_,
            create_only=create_only,
            **kwargs,
        )

    return _account_inner


@pytest.fixture
def admin_user(account: C[..., "Account"], session: Session) -> "Account":
    yield account(
        scopes=[Scopes.admin, Scopes.upload, Scopes.review, Scopes.submit],
        username="admin",
        password="adminadmin12",
        session=session,
    )


@pytest.fixture
def root_user(account: C[..., "Account"], session: Session) -> "Account":
    yield account(
        scopes=[Scopes.root, Scopes.admin, Scopes.upload, Scopes.review, Scopes.submit],
        username="root",
        password="rootroot1234",
        session=session,
    )


@pytest.fixture
def uploader(account: C[..., "Account"], session: Session) -> Account:
    return account(
        scopes=[Scopes.upload],
        session=session,
    )


@pytest.fixture
def reviewer(account: C[..., "Account"], session: Session) -> Account:
    return account(
        scopes=[Scopes.review],
        session=session,
    )


@pytest.fixture
def dataset(session: Session) -> C[Concatenate[bool, bool, Session | None, P], Dataset]:
    def _dataset_inner(
        is_approved: bool = True,
        is_removed: bool = False,
        session_: Session | None = None,
        **kwargs: P.kwargs,
    ) -> Dataset:
        if session_ is None:
            session_ = session
        return make_dataset(
            is_approved=is_approved, is_removed=is_removed, session_=session_, **kwargs
        )

    return _dataset_inner


@pytest.fixture(scope="module")
def dataset_module(
    session_module: Session,
) -> C[Concatenate[bool, bool, Session | None, P], Dataset]:
    def _dataset_inner(
        is_approved: bool = True,
        is_removed: bool = False,
        session_: Session | None = None,
        **kwargs: P.kwargs,
    ) -> Dataset:
        if session_ is None:
            session_ = session_module
        return make_dataset(
            is_approved=is_approved, is_removed=is_removed, session_=session_, **kwargs
        )

    return _dataset_inner


@pytest.fixture
def torrent(tmp_path: Path) -> C[P, Torrent]:

    def _torrent(**kwargs: P.kwargs) -> Torrent:
        kwargs = {**default_torrent(), **kwargs}
        if "tmp_path" not in kwargs:
            kwargs["tmp_path"] = kwargs.get("torrent_dir", tmp_path)
        return make_torrent(**kwargs)

    return _torrent


@pytest.fixture(scope="module")
def torrent_module(
    tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest
) -> C[P, Torrent]:
    tmp_path = tmp_path_factory.mktemp(str(request.node))

    def _torrent(**kwargs: P.kwargs) -> Torrent:
        kwargs = {**default_torrent(), **kwargs}
        if "tmp_path" not in kwargs:
            kwargs["tmp_path"] = kwargs.get("torrent_dir", tmp_path)
        return make_torrent(**kwargs)

    return _torrent


@pytest.fixture
def torrentfile(
    torrent: C[..., Torrent],
    session: Session,
    account: C[..., Account],
    tmp_path: Path,
) -> C[Concatenate[Account | None, Session | None, P], TorrentFile]:
    def _torrentfile_inner(
        extra_trackers: Optional[list[str]] = None,
        account_: Account | None = None,
        session_: Session | None = None,
        **kwargs: P.kwargs,
    ) -> TorrentFile:
        if session_ is None:
            session_ = session
        if account_ is None:
            account_ = account(scopes=[Scopes.upload], session_=session_, username="uploader")
        return make_torrentfile(
            tmp_path=tmp_path,
            torrent_=torrent,
            extra_trackers=extra_trackers,
            account_=account_,
            session_=session_,
            **kwargs,
        )

    return _torrentfile_inner


@pytest.fixture(scope="module")
def torrentfile_module(
    torrent_module: C[..., Torrent],
    session_module: Session,
    account_module: C[..., Account],
    tmp_path_factory: pytest.TempPathFactory,
    request: pytest.FixtureRequest,
) -> C[Concatenate[Account | None, Session | None, P], TorrentFile]:
    def _torrentfile_inner(
        extra_trackers: Optional[list[str]] = None,
        account_: Account | None = None,
        session_: Session | None = None,
        **kwargs: P.kwargs,
    ) -> TorrentFile:
        tmp_path = tmp_path_factory.mktemp(str(request.node))
        if session_ is None:
            session_ = session_module
        if account_ is None:
            account_ = account_module(
                scopes=[Scopes.upload], session_=session_, username="uploader"
            )
        return make_torrentfile(
            tmp_path=tmp_path,
            torrent_=torrent_module,
            extra_trackers=extra_trackers,
            account_=account_,
            session_=session_,
            **kwargs,
        )

    return _torrentfile_inner


@pytest.fixture
def upload(
    torrentfile: C[..., TorrentFile],
    account: C[..., Account],
    dataset: C[..., Dataset],
    session: Session,
) -> C[
    Concatenate[bool, TorrentFile | None, Account | None, Dataset | None, Session | None, P], Upload
]:
    def _upload_inner(
        is_approved: bool = True,
        torrentfile_: TorrentFile | None = None,
        account_: Account | None = None,
        dataset_: Dataset | None = None,
        session_: Session | None = None,
        **kwargs: P.kwargs,
    ) -> Upload:
        if session_ is None:
            session_ = session
        if account_ is None:
            account_ = account(scopes=[Scopes.upload], session_=session)
        if torrentfile_ is None:
            torrentfile_ = torrentfile(account_=account_, session_=session_)
        if dataset_ is None:
            dataset_ = dataset(is_approved=True, session=session_)
        return make_upload(session_, is_approved, torrentfile_, account_, dataset_, **kwargs)

    return _upload_inner


@pytest.fixture(scope="module")
def upload_module(
    torrentfile_module: C[..., TorrentFile],
    account_module: C[..., Account],
    dataset_module: C[..., Dataset],
    session_module: Session,
) -> C[
    Concatenate[bool, TorrentFile | None, Account | None, Dataset | None, Session | None, P], Upload
]:
    def _upload_inner(
        is_approved: bool = True,
        torrentfile_: TorrentFile | None = None,
        account_: Account | None = None,
        dataset_: Dataset | None = None,
        session_: Session | None = None,
        **kwargs: P.kwargs,
    ) -> Upload:
        if session_ is None:
            session_ = session_module
        if account_ is None:
            account_ = account_module(scopes=[Scopes.upload], session_=session_)
        if torrentfile_ is None:
            torrentfile_ = torrentfile_module(account_=account_, session_=session_)
        if dataset_ is None:
            dataset_ = dataset_module(is_approved=True, session=session_)
        return make_upload(session_, is_approved, torrentfile_, account_, dataset_, **kwargs)

    return _upload_inner


@pytest.fixture
def admin_token(admin_user: "Account") -> "Token":
    from sciop.api.auth import create_access_token
    from sciop.models import Token

    token = create_access_token(admin_user.account_id, expires_delta=timedelta(minutes=5))
    return Token(access_token=token)


@pytest.fixture
def root_token(root_user: "Account") -> "Token":
    from sciop.api.auth import create_access_token
    from sciop.models import Token

    token = create_access_token(root_user.account_id, expires_delta=timedelta(minutes=5))
    return Token(access_token=token)


@pytest.fixture
def admin_auth_header(admin_token: "Token") -> dict[L["Authorization"], str]:
    yield {"Authorization": f"Bearer {admin_token.access_token}"}


@pytest.fixture
def root_auth_header(root_token: "Token") -> dict[L["Authorization"], str]:
    yield {"Authorization": f"Bearer {root_token.access_token}"}


@pytest.fixture
def get_auth_header(session: Session) -> C[[str, str], dict[L["Authorization"], str]]:

    def _get_auth_header(
        username: str = "default", password: str = "averystrongpassword123"
    ) -> dict[L["Authorization"], str]:
        from sciop.api.auth import create_access_token
        from sciop.crud import get_account

        account = get_account(username=username, session=session)
        token = create_access_token(account.account_id, expires_delta=timedelta(minutes=5))
        return {"Authorization": f"Bearer {token}"}

    return _get_auth_header


@pytest.fixture()
def default_db(
    account: C[..., Account],
    dataset: C[..., Dataset],
    upload: C[..., Upload],
    session: Session,
    torrent: C[..., Torrent],
    torrentfile: C[..., TorrentFile],
) -> tuple[Account, Account, TorrentFile, Dataset, Upload]:
    admin = account(
        scopes=[Scopes.admin, Scopes.upload, Scopes.review],
        session_=session,
        username="admin",
        password="adminadmin12",
    )
    uploader = account(scopes=[Scopes.upload], session_=session, username="uploader")
    torrent = torrent()
    tfile = torrentfile(account_=uploader, session_=session, torrent=torrent)
    dataset_ = dataset(is_approved=True, session_=session)
    upload_ = upload(
        is_approved=True, torrentfile_=tfile, account_=uploader, dataset_=dataset_, session_=session
    )
    yield admin, uploader, tfile, dataset_, upload_


@pytest.fixture()
def torrent_pair(tmp_path: Path, torrent: C[..., Torrent]) -> tuple[Torrent, Torrent]:
    """Two torrents with same infohash but different trackers"""
    data_file = tmp_path / "data.bin"
    with open(data_file, "wb") as f:
        data = "".join([random.choice(string.ascii_letters) for _ in range(1024)])
        data = data.encode("utf-8")
        f.write(data)

    # make two torrents that should have identical infohash
    kwargs_1 = {
        "path": str(data_file),
        "name": "Default Torrent 1",
        "trackers": [["udp://example.com/announce"]],
        "comment": "My comment",
        "piece_size": 16384,
    }
    kwargs_2 = deepcopy(kwargs_1)
    kwargs_2["trackers"].append(["http://example.com/announce"])

    torrent_1 = torrent(**kwargs_1)
    torrent_2 = torrent(**kwargs_2)
    return torrent_1, torrent_2
