import hashlib
import random
import string
from collections.abc import Callable as C
from copy import deepcopy
from pathlib import Path
from typing import Concatenate, Optional, ParamSpec
from typing import Literal as L

import pytest
from faker import Faker
from sqlmodel import Session
from starlette.testclient import TestClient

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

fake = Faker()

P = ParamSpec("P")


@pytest.fixture
def default_account() -> dict:
    return {
        "username": "default",
        "password": "averystrongpassword123",
    }


@pytest.fixture
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


@pytest.fixture
def default_upload() -> dict:
    return {
        "method": "going and downloading it",
        "description": "here are files what more do you want from me",
        "torrent_short_hash": "defaultt",
    }


@pytest.fixture
def default_torrentfile() -> dict:
    files = [{"path": fake.file_name(), "size": random.randint(2**16, 2**24)} for i in range(5)]
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
        files = [{"path": fake.file_name(), "size": random.randint(2**16, 2**24)} for i in range(5)]
        hash_data = "".join([str(f) for f in files])
        hash_data = hash_data.encode("utf-8")
        return {
            "v1_infohash": hashlib.sha1(hash_data).hexdigest(),
            "v2_infohash": hashlib.sha256(hash_data).hexdigest(),
        }

    return _infohashes


@pytest.fixture
def default_torrent() -> dict:
    return {
        "path": "default.bin",
        "name": "Default Torrent",
        "trackers": [["udp://example.com/announce"]],
        "comment": "My comment",
        "piece_size": 16384,
    }


@pytest.fixture
def account(
    default_account: dict, session: Session
) -> C[Concatenate[list[Scopes] | None, Session | None, P], "Account"]:
    def _account(
        scopes: list[Scopes] = None,
        is_suspended: bool = False,
        session_: Session | None = None,
        **kwargs: P.kwargs,
    ) -> Account:
        if not session_:
            session_ = session

        scopes = [] if scopes is None else [Scope.get_item(s, session=session_) for s in scopes]
        kwargs = {**default_account.copy(), **kwargs}

        account_ = crud.get_account(session=session_, username=kwargs["username"])
        if not account_:
            account_ = AccountCreate(**kwargs)
            account_ = crud.create_account(session=session_, account_create=account_)
        account_.scopes = scopes
        account_.is_suspended = is_suspended
        session_.add(account_)
        session_.commit()
        session_.flush()
        session_.refresh(account_)
        return account_

    yield _account


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
def dataset(
    default_dataset: dict, session: Session
) -> C[Concatenate[bool, bool, Session | None, P], Dataset]:
    def _dataset(
        is_approved: bool = True,
        is_removed: bool = False,
        session_: Session | None = None,
        **kwargs: P.kwargs,
    ) -> Dataset:
        if session_ is None:
            session_ = session
        kwargs = {**default_dataset, **kwargs}

        created = DatasetCreate(**kwargs)
        dataset = crud.create_dataset(
            session=session_, dataset_create=created, is_approved=is_approved, is_removed=is_removed
        )
        return dataset

    return _dataset


@pytest.fixture
def torrent(default_torrent: dict, tmp_path: Path) -> C[P, Torrent]:

    def _torrent(**kwargs: P.kwargs) -> Torrent:
        kwargs = {**default_torrent.copy(), **kwargs}
        file_in_torrent = Path(default_torrent["path"])
        if not file_in_torrent.is_absolute():
            file_in_torrent = tmp_path / file_in_torrent

        hash_data = "".join([random.choice(string.ascii_letters) for _ in range(1024)])
        hash_data = hash_data.encode("utf-8")
        with open(file_in_torrent, "wb") as f:
            f.write(hash_data)
        kwargs["path"] = file_in_torrent

        t = Torrent(**kwargs)
        t.generate()
        return t

    return _torrent


@pytest.fixture
def torrentfile(
    default_torrentfile: dict,
    torrent: C[..., Torrent],
    session: Session,
    account: C[..., Account],
    tmp_path: Path,
) -> C[Concatenate[Account | None, Session | None, P], TorrentFile]:
    def _torrentfile(
        extra_trackers: Optional[list[str]] = None,
        account_: Account | None = None,
        session_: Session | None = None,
        **kwargs: P.kwargs,
    ) -> TorrentFile:
        if session_ is None:
            session_ = session
        if account_ is None:
            account_ = account(scopes=[Scopes.upload], session_=session_, username="uploader")
        passed_announce_urls = "announce_urls" in kwargs
        kwargs = deepcopy({**default_torrentfile, **kwargs})

        file_in_torrent = tmp_path / "default.bin"
        hash_data = random.randbytes(kwargs["total_size"])
        with open(file_in_torrent, "wb") as f:
            f.write(hash_data)

        t = torrent(path=file_in_torrent)

        if kwargs.get("v1_infohash", None) is None:
            kwargs["v1_infohash"] = t.infohash
        if kwargs.get("v2_infohash", None) is None:
            kwargs["v2_infohash"] = t.v2_infohash

        if extra_trackers is not None:
            kwargs["announce_urls"].extend(extra_trackers)
        elif not passed_announce_urls:
            kwargs["announce_urls"].append(fake.url(schemes=["udp"]))

        tf = TorrentFileCreate(**kwargs)
        tf.filesystem_path.parent.mkdir(exist_ok=True, parents=True)
        t.write(tf.filesystem_path, overwrite=True)
        created = crud.create_torrent(session=session_, created_torrent=tf, account=account_)
        return created

    return _torrentfile


@pytest.fixture
def upload(
    default_upload: dict,
    torrentfile: C[..., TorrentFile],
    account: C[..., Account],
    dataset: C[..., Dataset],
    session: Session,
) -> C[
    Concatenate[bool, TorrentFile | None, Account | None, Dataset | None, Session | None, P], Upload
]:
    def _upload(
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

        kwargs = {**default_upload, **kwargs}
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

    return _upload


@pytest.fixture
def admin_token(client: "TestClient", admin_user: "Account", session: Session) -> "Token":
    from sciop.config import config
    from sciop.models import Token

    session.add(admin_user)
    session.commit()

    response = client.post(
        config.api_prefix + "/login",
        data={"username": "admin", "password": "adminadmin12"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    yield Token(**response.json())


@pytest.fixture
def root_token(client: "TestClient", root_user: "Account", session: Session) -> "Token":
    from sciop.config import config
    from sciop.models import Token

    session.add(root_user)
    session.commit()

    response = client.post(
        config.api_prefix + "/login",
        data={"username": "root", "password": "rootroot1234"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    yield Token(**response.json())


@pytest.fixture
def admin_auth_header(admin_token: "Token") -> dict[L["Authorization"], str]:
    yield {"Authorization": f"Bearer {admin_token.access_token}"}


@pytest.fixture
def root_auth_header(root_token: "Token") -> dict[L["Authorization"], str]:
    yield {"Authorization": f"Bearer {root_token.access_token}"}


@pytest.fixture
def get_auth_header(client: "TestClient") -> C[[str, str], dict[L["Authorization"], str]]:
    from sciop.config import config

    def _get_auth_header(
        username: str = "default", password: str = "averystrongpassword123"
    ) -> dict[L["Authorization"], str]:
        response = client.post(
            config.api_prefix + "/login",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        token = Token(**response.json())
        return {"Authorization": f"Bearer {token.access_token}"}

    return _get_auth_header


@pytest.fixture()
def default_db(
    account: C[..., Account],
    dataset: C[..., Dataset],
    upload: C[..., Upload],
    session: Session,
    torrentfile: C[..., TorrentFile],
) -> tuple[Account, Account, TorrentFile, Dataset, Upload]:
    admin = account(
        scopes=[Scopes.admin, Scopes.upload, Scopes.review],
        session_=session,
        username="admin",
        password="adminadmin12",
    )
    uploader = account(scopes=[Scopes.upload], session_=session, username="uploader")
    tfile = torrentfile(account_=uploader, session_=session)
    dataset_ = dataset(is_approved=True, session_=session)
    upload_ = upload(
        is_approved=True, torrentfile_=tfile, account_=uploader, dataset_=dataset_, session_=session
    )
    yield admin, uploader, tfile, dataset_, upload_
