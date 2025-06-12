import hashlib
import random
import string
from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Optional, ParamSpec
from typing import Callable as C

import bencodepy
import numpy as np
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
    Torrent,
    TorrentFile,
    TorrentFileCreate,
    Upload,
    UploadCreate,
)

fake = Faker()
P = ParamSpec("P")


_HASH_CACHE = {}
"""
map of passwords to hashes
o ya we're attackin ourselves now
"""


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


def default_torrent() -> dict:
    return {
        "path": "default.bin",
        "name": "Default Torrent",
        "trackers": [["udp://example.com/announce"]],
        "comment": "My comment",
        "piece_size": 16384,
    }


def make_account(
    session_: Session,
    scopes: list[Scopes] = None,
    is_suspended: bool = False,
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


def make_dataset(
    session_: Session,
    is_approved: bool = True,
    is_removed: bool = False,
    **kwargs: P.kwargs,
) -> Dataset:
    kwargs = {**default_dataset(), **kwargs}

    created = DatasetCreate(**kwargs)
    dataset = crud.create_dataset(
        session=session_, dataset_create=created, is_approved=is_approved, is_removed=is_removed
    )
    return dataset


def make_torrent(path: Path, tmp_path: Path | None = None, **kwargs: Any) -> Torrent:
    """

    Args:
        path (Path): path to a file to make a torrent out of.
            If no such path exists, it will be created with random letters
        tmp_path (Path | None): path to a temporary directory that the file is contained in,
            if path is relative.
        **kwargs:

    Returns:

    """
    file_in_torrent = Path(path)
    if not file_in_torrent.is_absolute() and tmp_path:
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


def make_torrentfile(
    session_: Session,
    tmp_path: Path,
    torrent_: C[[...], Torrent] = make_torrent,
    extra_trackers: Optional[list[str]] = None,
    n_files: int = 1,
    account_: Account | None = None,
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

        t = torrent_(tmp_path=tmp_path, path=file_in_torrent)

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


def make_upload(
    session_: Session,
    is_approved: bool = True,
    torrentfile_: TorrentFile | None = None,
    account_: Account | None = None,
    dataset_: Dataset | None = None,
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


@dataclass
class Fabricator:
    """Convenience class to fabricate objects with the same session"""

    session: Session

    @wraps(make_account)
    def account(self, **kwargs: P.kwargs) -> Account:
        return make_account(session_=self.session, **kwargs)

    @wraps(make_dataset)
    def dataset(self, **kwargs: P.kwargs) -> Dataset:
        return make_dataset(session_=self.session, **kwargs)

    @wraps(make_upload)
    def upload(self, **kwargs: P.kwargs) -> Upload:
        return make_upload(session_=self.session, **kwargs)

    @wraps(make_torrent)
    def torrent(self, **kwargs: P.kwargs) -> Torrent:
        return make_torrent(**kwargs)

    @wraps(make_torrentfile)
    def torrentfile(self, **kwargs: P.kwargs) -> TorrentFile:
        return make_torrentfile(session_=self.session, **kwargs)
