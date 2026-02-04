import random
import string
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from random import randint
from typing import Any, Optional, ParamSpec
from typing import Callable as C

import numpy as np
from faker import Faker
from sqlmodel import Session
from torrent_models import Torrent, TorrentCreate

from sciop import crud
from sciop.models import (
    Account,
    AccountCreate,
    Dataset,
    DatasetCreate,
    DatasetPart,
    DatasetPartCreate,
    FileInTorrentCreate,
    Scope,
    TorrentFile,
    TorrentFileCreate,
    Upload,
    UploadCreate,
)
from sciop.types import Scopes

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


def default_dataset_part() -> dict:
    return {
        "part_slug": "default-part",
        "description": "Some part of a dataset, who knows!",
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
    account_: Account | None = None,
    **kwargs: P.kwargs,
) -> Dataset:
    kwargs = {**default_dataset(), **kwargs}

    created = DatasetCreate(**kwargs)
    dataset = crud.create_dataset(
        session=session_,
        dataset_create=created,
        is_approved=is_approved,
        is_removed=is_removed,
        current_account=account_,
    )
    return dataset


def make_dataset_part(
    session_: Session,
    account_: Account,
    dataset_: Dataset,
    is_approved: bool = True,
    is_removed: bool = False,
    **kwargs: P.kwargs,
) -> DatasetPart:
    kwargs = {**default_dataset_part(), **kwargs}
    create = DatasetPartCreate(**kwargs)

    part = crud.create_dataset_part(
        session=session_, dataset_part=create, account=account_, dataset=dataset_, commit=False
    )
    part.is_approved = is_approved
    part.is_removed = is_removed
    session_.add(part)
    session_.commit()
    session_.refresh(part)
    return part


def make_torrent(path: Path | list[Path], tmp_path: Path | None = None, **kwargs: Any) -> Torrent:
    """
    This function makes decreasing sense over time... simplify this.

    Args:
        path (Path): path to a file to make a torrent out of.
            If no such path exists, it will be created with random letters
        tmp_path (Path | None): path to a temporary directory that the file is contained in,
            if path is relative.
        **kwargs:

    Returns:

    """
    if not isinstance(path, list):
        file_in_torrent = Path(path)
        if not file_in_torrent.is_absolute() and tmp_path:
            file_in_torrent = tmp_path / file_in_torrent

        if not file_in_torrent.exists():
            hash_data = "".join([random.choice(string.ascii_letters) for _ in range(1024)])
            hash_data = hash_data.encode("utf-8")
            with open(file_in_torrent, "wb") as f:
                f.write(hash_data)
        kwargs["paths"] = [file_in_torrent]
    else:
        kwargs["paths"] = path
    kwargs["path_root"] = tmp_path
    kwargs["piece_length"] = 16 * (2**10)

    t = TorrentCreate(**kwargs)
    t = t.generate(version="hybrid")
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
        announce_urls_nested = t.announce_list
        if announce_urls_nested is None:
            announce_urls_nested = [[]]
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

            t = torrent_(
                tmp_path=tmp_path,
                path=file_in_torrent,
                url_list=kwargs.get("webseeds"),
            )
        else:
            file_in_torrent = tmp_path
            each_file = np.floor(kwargs["total_size"] / n_files)
            sizes = [each_file] * n_files
            # make last file pick up the remainder
            sizes[-1] += kwargs["total_size"] - np.sum(sizes)
            paths = []  # plain paths to make torrent
            files = []  # file objects with sizes for db
            for i, size in enumerate(sizes):
                hash_data = generator.bytes(size)
                paths.append(Path(f"{i}.bin"))
                files.append({"path": f"{i}.bin", "size": size})
                with open(file_in_torrent / f"{i}.bin", "wb") as f:
                    f.write(hash_data)
            kwargs["files"] = files
            t = torrent_(
                tmp_path=tmp_path,
                path=paths,
                url_list=kwargs.get("webseeds"),
            )

    if kwargs.get("v1_infohash", None) is None:
        kwargs["v1_infohash"] = t.v1_infohash
    if kwargs.get("v2_infohash", None) is None:
        kwargs["v2_infohash"] = t.v2_infohash
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
        t.write(tf.filesystem_path)
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
        if torrentfile_:
            kwargs["infohash"] = torrentfile_.infohash
        elif "name" in kwargs:
            kwargs["infohash"] = kwargs["name"]

    created = UploadCreate(**kwargs)
    created = crud.create_upload(
        session=session_, created_upload=created, dataset=dataset_, account=account_
    )
    created.is_approved = is_approved
    session_.add(created)
    session_.commit()
    session_.refresh(created)
    return created


def random_upload(
    name: str,
    account: "Account",
    dataset: "Dataset",
    session: Session,
    fake: Faker | None = None,
    is_approved: bool | None = None,
    is_removed: bool | None = None,
    commit: bool = True,
    torrent_kwargs: dict | None = None,
    torrentfile_kwargs: dict | None = None,
) -> "Upload":
    if not fake:
        fake = Faker()
    if torrent_kwargs is None:
        torrent_kwargs = {}
    if torrentfile_kwargs is None:
        torrentfile_kwargs = {}

    tmp_parent = Path("__tmp__")
    tmp_parent.mkdir(exist_ok=True)
    torrent_file = name + str(fake.file_name(extension="bin"))
    with open(tmp_parent / torrent_file, "wb") as tfile:
        hash_data = "".join([random.choice(string.ascii_letters) for _ in range(1024)])
        hash_data = hash_data.encode("utf-8")
        tfile.write(hash_data)

    file_size = (tmp_parent / torrent_file).stat().st_size

    torrent = TorrentCreate(
        paths=[torrent_file],
        path_root=tmp_parent,
        trackers=["udp://opentracker.io:6969/announce"],
        comment="My comment",
        piece_length=16384,
        info={"name": f"test_{name}"},
        **torrent_kwargs,
    )
    torrent = torrent.generate(version="hybrid")

    created_torrent = TorrentFileCreate(
        file_name=torrent_file,
        v1_infohash=torrent.v1_infohash,
        v2_infohash=torrent.v2_infohash,
        version="hybrid",
        total_size=16384 * 4,
        piece_size=16384,
        torrent_size=64,
        files=[FileInTorrentCreate(path=torrent_file, size=file_size)],
        announce_urls=["udp://opentracker.io:6969/announce"],
        **torrentfile_kwargs,
    )
    created_torrent.filesystem_path.parent.mkdir(parents=True, exist_ok=True)
    torrent.write(created_torrent.filesystem_path)
    created_torrent = crud.create_torrent(
        session=session, created_torrent=created_torrent, account=account
    )
    for tracker_link in created_torrent.tracker_links:
        tracker_link.seeders = random.randint(1, 100)
        tracker_link.leechers = random.randint(1, 100)
    session.add(created_torrent)
    session.commit()

    upload = UploadCreate(
        method="I downloaded it",
        description="Its all here bub",
        infohash=created_torrent.infohash,
    )

    created_upload = crud.create_upload(
        session=session, created_upload=upload, dataset=dataset, account=account
    )
    if is_approved is not None:
        created_upload.is_approved = is_approved
    else:
        created_upload.is_approved = random.random() > 0.5
    if is_removed is not None:
        created_upload.is_removed = is_removed

    if commit:
        session.add(created_upload)
        session.commit()
        session.refresh(created_upload)
    return created_upload


def random_dataset(
    session: Session, account: Account | None = None, commit: bool = True, fake: Faker | None = None
) -> Dataset:
    if not fake:
        fake = Faker()

    from sciop.models import DatasetCreate, DatasetPartCreate, ExternalIdentifierCreate
    from sciop.types import AccessType, Scarcity, Threat

    dataset_fake = Faker()

    title = fake.unique.bs()
    slug = title.lower().replace(" ", "-")

    parts = []
    base_path = Path(fake.unique.file_path(depth=2, extension=tuple()))

    for i in range(random.randint(1, 5)):
        part_slug = base_path / dataset_fake.unique.file_name(extension="")
        paths = [str(part_slug / dataset_fake.unique.file_name()) for i in range(5)]
        part = DatasetPartCreate(part_slug=str(part_slug), paths=paths)
        parts.append(part)

    tags = []
    for _ in range(3):
        tag = fake.word().lower()
        while len(tag) < 3:
            tag = fake.word().lower()
        tags.append(tag)

    ds = DatasetCreate(
        slug=slug,
        title=title,
        publisher=fake.company(),
        homepage=fake.url(),
        description=fake.text(1000),
        priority="low",
        source="web",
        source_available=random.choice([True, False]),
        source_access=random.choice(list(AccessType.__members__.values())),
        threat=random.choice(list(Threat.__members__.values())),
        scarcity=random.choice(list(Scarcity.__members__.values())),
        dataset_created_at=datetime.now(UTC),
        dataset_updated_at=datetime.now(UTC),
        urls=[fake.url() for _ in range(3)],
        tags=tags,
        external_identifiers=[
            ExternalIdentifierCreate(
                type="doi",
                identifier=(
                    f"10.{randint(1000, 9999)}/{fake.word().lower()}.{randint(10000, 99999)}"
                ),
            )
        ],
        parts=parts,
    )

    ds = crud.create_dataset(session=session, dataset_create=ds, current_account=account)
    timestamp = datetime.now(UTC) - timedelta(minutes=random.randint(60, 60 * 24 * 7))
    ds.created_at = timestamp
    ds.updated_at = timestamp

    ds.is_approved = random.random() > 0.1
    for part in ds.parts:
        part.account = account
        part.is_approved = random.random() > 0.5

    if commit:
        session.add(ds)
        session.commit()
        session.refresh(ds)
    return ds


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

    @wraps(random_dataset)
    def random_dataset(self, **kwargs: P.kwargs) -> Dataset | DatasetCreate:
        return random_dataset(session=self.session, **kwargs)

    @wraps(random_upload)
    def random_upload(self, **kwargs: P.kwargs) -> Upload:
        return random_upload(session=self.session, **kwargs)
