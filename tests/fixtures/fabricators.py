import hashlib
import random
import string
from collections.abc import Callable as C
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any, Concatenate, Optional, ParamSpec
from typing import Literal as L

import bencodepy
import numpy as np
import pytest
from faker import Faker
from sqlmodel import Session

from sciop import crud
from sciop.models import (
    Account,
    AccountCreate,
    Dataset,
    DatasetCreate,
    Scope,
    Scopes,
    Token,
    Torrent,
    TorrentFile,
    TorrentFileCreate,
    Upload,
    UploadCreate,
)

from .paths import TMP_DIR

fake = Faker()

P = ParamSpec("P")

__all__ = [
    "account",
    "account_module",
    "admin_auth_header",
    "admin_user",
    "admin_token",
    "dataset",
    "dataset_module",
    "default_account",
    "default_created_torrent",
    "default_dataset",
    "default_db",
    "default_upload",
    "default_torrent",
    "default_torrentfile",
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


def default_account() -> dict:
    return {
        "username": "default",
        "password": "averystrongpassword123",
    }


def default_dataset() -> dict:
    return {
        "title": "A Default Dataset",
        "slug": "default",
        "publisher": "Default Datasets Incorporated",
        "homepage": "https://example.com",
        "description": "You might not like it folks but this is it, "
        "this is the peak of default datasets",
        "source": "web",
        "urls": ["https://example.com/1", "https://example.com/2"],
        "tags": ["default", "dataset", "tags"],
    }


def default_upload() -> dict:
    return {
        "method": "going and downloading it",
        "description": "here are files what more do you want from me",
        "torrent_short_hash": "defaultt",
    }


def default_torrentfile() -> dict:
    files = [
        {
            "path": fake.file_name(),
            "size": np.random.default_rng().integers(16 * (2**10), 64 * (2**10)),
        }
        for i in range(5)
    ]
    return {
        "file_name": "default.torrent",
        "file_hash": "abcdefghijklmnop",
        "version": "hybrid",
        "short_hash": "defaultt",  # needs to be 8 chars lol
        "total_size": sum(f["size"] for f in files),
        "piece_size": 16384,
        "torrent_size": 64,
        "files": files,
        "announce_urls": ["http://example.com/announce", "udp://example.com/announce"],
    }


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


def default_torrent() -> dict:
    return {
        "path": "default.bin",
        "name": "Default Torrent",
        "trackers": [["udp://example.com/announce"]],
        "comment": "My comment",
        "piece_size": 16384,
    }


_HASH_CACHE = {}
"""
map of passwords to hashes
o ya we're attackin ourselves now
"""


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
        return _account(
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
        return _account(
            scopes=scopes,
            is_suspended=is_suspended,
            session_=session_,
            create_only=create_only,
            **kwargs,
        )

    return _account_inner


def _account(
    scopes: list[Scopes] = None,
    is_suspended: bool = False,
    session_: Session | None = None,
    create_only: bool = False,
    **kwargs: P.kwargs,
) -> Account:
    global _HASH_CACHE
    scopes = [] if scopes is None else [Scope.get_item(s, session=session_) for s in scopes]
    kwargs = {**default_account(), **kwargs}

    account_ = None
    if not create_only:
        account_ = crud.get_account(session=session_, username=kwargs["username"])
    if not account_:
        account_create = AccountCreate(**kwargs)
        if kwargs.get("password") not in _HASH_CACHE:
            account_ = crud.create_account(session=session_, account_create=account_create)
            _HASH_CACHE[kwargs.get("password")] = account_.hashed_password
        else:
            account_ = Account.model_validate(
                account_create, update={"hashed_password": _HASH_CACHE[kwargs.get("password")]}
            )

    account_.scopes = scopes
    account_.is_suspended = is_suspended
    session_.add(account_)
    session_.commit()
    session_.flush()
    session_.refresh(account_)
    return account_


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
        return _dataset(is_approved=is_approved, is_removed=is_removed, session_=session_, **kwargs)

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
        return _dataset(is_approved=is_approved, is_removed=is_removed, session_=session_, **kwargs)

    return _dataset_inner


def _dataset(
    is_approved: bool = True,
    is_removed: bool = False,
    session_: Session | None = None,
    **kwargs: P.kwargs,
) -> Dataset:
    kwargs = {**default_dataset(), **kwargs}

    created = DatasetCreate(**kwargs)
    dataset = crud.create_dataset(
        session=session_, dataset_create=created, is_approved=is_approved, is_removed=is_removed
    )
    return dataset


def _make_torrent(tmp_path: Path, **kwargs: Any) -> Torrent:
    file_in_torrent = Path(kwargs["path"])
    if not file_in_torrent.is_absolute():
        file_in_torrent = tmp_path / file_in_torrent

    if not file_in_torrent.exists():
        hash_data = "".join([random.choice(string.ascii_letters) for _ in range(1024)])
        hash_data = hash_data.encode("utf-8")
        with open(file_in_torrent, "wb") as f:
            f.write(hash_data)
    kwargs["path"] = file_in_torrent

    t = Torrent(**kwargs)
    t.generate()
    return t


@pytest.fixture
def torrent(tmp_path: Path) -> C[P, Torrent]:

    def _torrent(**kwargs: P.kwargs) -> Torrent:
        kwargs = {**default_torrent(), **kwargs}
        return _make_torrent(tmp_path=kwargs.get("torrent_dir", tmp_path), **kwargs)

    return _torrent


@pytest.fixture(scope="module")
def torrent_module(
    tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest
) -> C[P, Torrent]:
    tmp_path = tmp_path_factory.mktemp(str(request.node))

    def _torrent(**kwargs: P.kwargs) -> Torrent:
        kwargs = {**default_torrent(), **kwargs}
        return _make_torrent(tmp_path=kwargs.get("torrent_dir", tmp_path), **kwargs)

    return _torrent


@pytest.fixture
def torrentfile(
    torrent: C[..., Torrent],
    session: Session,
    account: C[..., Account],
    tmp_path: Path,
    default_created_torrent: Torrent,
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
        return _torrentfile(
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
    default_created_torrent: Torrent,
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
        return _torrentfile(
            tmp_path=tmp_path,
            torrent_=torrent_module,
            extra_trackers=extra_trackers,
            account_=account_,
            session_=session_,
            **kwargs,
        )

    return _torrentfile_inner


def _torrentfile(
    tmp_path: Path,
    torrent_: C[[Any, ...], Torrent],
    extra_trackers: Optional[list[str]] = None,
    n_files: int = 1,
    account_: Account | None = None,
    session_: Session | None = None,
    **kwargs: P.kwargs,
) -> TorrentFile:
    passed_announce_urls = "announce_urls" in kwargs or "torrent" in kwargs
    kwargs = deepcopy({**default_torrentfile(), **kwargs})
    generator = np.random.default_rng()

    if "torrent" in kwargs:
        t: Torrent = kwargs.pop("torrent")
        announce_urls_nested = t.trackers
        announce_urls = []
        for tier in announce_urls_nested:
            announce_urls.extend(tier)
        kwargs["announce_urls"] = announce_urls

    else:
        if n_files == 1:
            file_in_torrent = tmp_path / "default.bin"
            hash_data = generator.bytes(kwargs["total_size"])
            with open(file_in_torrent, "wb") as f:
                f.write(hash_data)
            kwargs["files"] = [{"path": "default.bin", "size": kwargs["total_size"]}]
        else:
            file_in_torrent = tmp_path
            each_file = np.floor(kwargs["total_size"] / n_files)
            sizes = [each_file] * n_files
            # make last file pick up the remainder
            sizes[-1] += kwargs["total_size"] - np.sum(sizes)
            files = []
            for i, size in enumerate(sizes):
                hash_data = generator.bytes(size)
                files.append({"path": f"{i}.bin", "size": size})
                with open(file_in_torrent / f"{i}.bin", "wb") as f:
                    f.write(hash_data)
            kwargs["files"] = files

        t = torrent_(path=file_in_torrent)

    if kwargs.get("v1_infohash", None) is None:
        kwargs["v1_infohash"] = t.infohash
    if kwargs.get("v2_infohash", None) is None:
        if t.v2_infohash is None:
            v2_infohash = hashlib.sha256(bencodepy.encode(t.metainfo["info"])).hexdigest()
        else:
            v2_infohash = t.v2_infohash
        kwargs["v2_infohash"] = v2_infohash
    elif "v2_infohash" in kwargs and not kwargs["v2_infohash"]:
        # set to `False`, exclude v2_infohash
        del kwargs["v2_infohash"]

    if extra_trackers is not None:
        kwargs["announce_urls"].extend(extra_trackers)
    elif not passed_announce_urls:
        kwargs["announce_urls"].append(fake.url(schemes=["udp"]))

    tf = TorrentFileCreate(**kwargs)
    if not tf.filesystem_path.exists():
        tf.filesystem_path.parent.mkdir(exist_ok=True, parents=True)
        t.write(tf.filesystem_path, overwrite=True)
    created = crud.create_torrent(session=session_, created_torrent=tf, account=account_)
    return created


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
        return _upload(is_approved, torrentfile_, account_, dataset_, session_, **kwargs)

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
        return _upload(is_approved, torrentfile_, account_, dataset_, session_, **kwargs)

    return _upload_inner


def _upload(
    is_approved: bool = True,
    torrentfile_: TorrentFile | None = None,
    account_: Account | None = None,
    dataset_: Dataset | None = None,
    session_: Session | None = None,
    **kwargs: P.kwargs,
) -> Upload:
    kwargs = {**default_upload(), **kwargs}
    if "infohash" not in kwargs:
        kwargs["infohash"] = torrentfile_.infohash
    created = UploadCreate(**kwargs)
    created = crud.create_upload(
        session=session_, created_upload=created, dataset=dataset_, account=account_
    )
    created.is_approved = is_approved
    session_.add(created)
    session_.commit()
    session_.refresh(created)
    return created


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


@pytest.fixture(scope="session")
def default_created_torrent() -> Torrent:
    # only make this once for yno perf

    torrent = _make_torrent(TMP_DIR, **default_torrent())
    tf = TorrentFileCreate(
        file_name="default.torrent",
        v1_infohash=torrent.infohash,
        v2_infohash=torrent.v2_infohash,
        version="hybrid",
        total_size=torrent.size,
        piece_size=torrent.piece_size,
        files=[{"path": "default.bin", "size": 100}],
        announce_urls=["udp://example.com:6969/announce"],
    )

    tf.filesystem_path.parent.mkdir(exist_ok=True, parents=True)
    torrent.write(tf.filesystem_path, overwrite=True)
    return torrent


@pytest.fixture()
def default_db(
    account: C[..., Account],
    dataset: C[..., Dataset],
    upload: C[..., Upload],
    session: Session,
    torrentfile: C[..., TorrentFile],
    default_created_torrent: Torrent,
) -> tuple[Account, Account, TorrentFile, Dataset, Upload]:
    admin = account(
        scopes=[Scopes.admin, Scopes.upload, Scopes.review],
        session_=session,
        username="admin",
        password="adminadmin12",
    )
    uploader = account(scopes=[Scopes.upload], session_=session, username="uploader")
    tfile = torrentfile(account_=uploader, session_=session, torrent=default_created_torrent)
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
