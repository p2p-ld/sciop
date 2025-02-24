from typing import Optional

from sqlmodel import Session, select

from sciop.api.auth import get_password_hash, verify_password
from sciop.models import (
    Account,
    AccountCreate,
    AuditLog,
    Dataset,
    DatasetCreate,
    DatasetPart,
    DatasetPartCreate,
    DatasetPath,
    DatasetURL,
    ExternalIdentifier,
    FileInTorrent,
    ModerationAction,
    Tag,
    TorrentFile,
    TorrentFileCreate,
    TrackerInTorrent,
    Upload,
    UploadCreate,
)


def create_account(*, session: Session, account_create: AccountCreate) -> Account:
    db_obj = Account.model_validate(
        account_create, update={"hashed_password": get_password_hash(account_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_account(*, session: Session, username: str) -> Account | None:
    statement = select(Account).where(Account.username == username)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, username: str, password: str) -> Account | None:
    db_user = get_account(session=session, username=username)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def create_dataset(
    *, session: Session, dataset_create: DatasetCreate, current_account: Optional[Account] = None
) -> Dataset:
    enabled = current_account is not None and current_account.has_scope("submit")
    urls = [DatasetURL(url=url) for url in dataset_create.urls]
    external_identifiers = [
        ExternalIdentifier(type=e.type, identifier=e.identifier)
        for e in dataset_create.external_identifiers
    ]
    parts = [
        create_dataset_part(
            session=session, account=current_account, dataset_part=part, commit=False
        )
        for part in dataset_create.parts
    ]

    existing_tags = session.exec(select(Tag).filter(Tag.tag.in_(dataset_create.tags))).all()
    existing_tag_str = set([e.tag for e in existing_tags])
    new_tags = set(dataset_create.tags) - existing_tag_str
    new_tags = [Tag(tag=tag) for tag in new_tags]
    tags = [*existing_tags, *new_tags]

    db_obj = Dataset.model_validate(
        dataset_create,
        update={
            "enabled": enabled,
            "account": current_account,
            "urls": urls,
            "tags": tags,
            "external_identifiers": external_identifiers,
            "parts": parts,
        },
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def create_dataset_part(
    *,
    session: Session,
    dataset_part: DatasetPartCreate,
    dataset: Dataset | None = None,
    account: Account | None = None,
    commit: bool = True,
) -> DatasetPart:
    paths = [DatasetPath(path=str(path)) for path in dataset_part.paths]
    enabled = bool(account) and account.has_scope("submit")
    part = DatasetPart.model_validate(
        dataset_part,
        update={
            "paths": paths,
            "dataset": dataset,
            "account": account,
            "enabled": enabled,
        },
    )
    session.add(part)
    if commit:
        session.commit()
        session.refresh(part)
    return part


def get_dataset(*, session: Session, dataset_slug: str) -> Dataset | None:
    """Get a dataset by its slug"""
    statement = select(Dataset).where(Dataset.slug == dataset_slug)
    session_dataset = session.exec(statement).first()
    return session_dataset


def get_dataset_part(
    *, session: Session, dataset_slug: str, dataset_part_slug: str
) -> Optional[DatasetPart]:
    statement = (
        select(DatasetPart)
        .join(Dataset)
        .filter(DatasetPart.part_slug == dataset_part_slug, Dataset.slug == dataset_slug)
    )
    part = session.exec(statement).first()
    return part


def get_dataset_parts(
    *, session: Session, dataset_slug: str, dataset_part_slugs: list[str]
) -> Optional[list[DatasetPart]]:
    statement = (
        select(DatasetPart)
        .join(Dataset)
        .filter(DatasetPart.part_slug.in_(dataset_part_slugs), Dataset.slug == dataset_slug)
    )
    parts = session.exec(statement).all()
    return parts


def get_approved_datasets(*, session: Session) -> list[Dataset]:
    statement = select(Dataset).where(Dataset.enabled == True)
    return session.exec(statement).all()


def get_approved_datasets_from_tag(*, session: Session, tag: str) -> list[Upload]:
    statement = select(Dataset).where(Dataset.enabled == True, Dataset.tags.any(tag=tag))
    return session.exec(statement).all()


def get_review_datasets(*, session: Session) -> list[Dataset]:
    statement = select(Dataset).where(Dataset.enabled == False)
    datasets = session.exec(statement).all()
    return datasets


def get_review_datasets_from_tag(*, session: Session, tag: str) -> list[Upload]:
    statement = select(Dataset).where(Dataset.enabled == False, Dataset.tags.any(tag=tag))
    return session.exec(statement).all()


def get_review_uploads(*, session: Session) -> list[Upload]:
    statement = select(Upload).where(Upload.enabled == False)
    uploads = session.exec(statement).all()
    return uploads


def get_torrent_from_infohash(
    *,
    session: Session,
    infohash: Optional[str] = None,
    v1: Optional[str] = None,
    v2: Optional[str] = None,
) -> Optional[TorrentFile]:
    """
    Get a torrent from one of its infohashes.

    If the generic ``infohash`` is passed, it can be v1, v2, or the short hash.
    Otherwise, v1 and v2 can be passed, individually or together.
    """
    if infohash:
        if len(infohash) == 8:
            return get_torrent_from_short_hash(short_hash=infohash, session=session)
        elif len(infohash) == 40:
            v1 = infohash
        elif len(infohash) == 64:
            v2 = infohash
        else:
            raise ValueError("Infohash is not a short hash, v1, or v2 infohash")

    if v1 and v2:
        statement = select(TorrentFile).filter(
            (TorrentFile.v1_infohash == v1) | (TorrentFile.v2_infohash == v2)
        )
    elif v1:
        statement = select(TorrentFile).filter(TorrentFile.v1_infohash == v1)
    elif v2:
        statement = select(TorrentFile).filter(TorrentFile.v2_infohash == v2)
    else:
        raise ValueError("Either a v1 or a v2 infohash must be passed")

    value = session.exec(statement).first()
    return value


def get_torrent_from_short_hash(*, short_hash: str, session: Session) -> Optional[TorrentFile]:
    statement = select(TorrentFile).where(TorrentFile.short_hash == short_hash)
    value = session.exec(statement).first()
    return value


def create_torrent(
    *, session: Session, created_torrent: TorrentFileCreate, account: Account
) -> TorrentFile:
    trackers = [TrackerInTorrent(url=url) for url in created_torrent.trackers]
    files = [FileInTorrent(path=file.path, size=file.size) for file in created_torrent.files]
    db_obj = TorrentFile.model_validate(
        created_torrent, update={"trackers": trackers, "files": files, "account": account}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def create_upload(
    *, session: Session, created_upload: UploadCreate, account: Account, dataset: Dataset
) -> Upload:
    torrent = get_torrent_from_infohash(session=session, infohash=created_upload.torrent_infohash)
    update = {
        "torrent": torrent,
        "account": account,
        "dataset": dataset,
        "infohash": created_upload.torrent_infohash,
    }
    if created_upload.part_slugs:
        update["dataset_parts"] = get_dataset_parts(
            session=session, dataset_slug=dataset.slug, dataset_part_slugs=created_upload.part_slugs
        )

    db_obj = Upload.model_validate(created_upload, update=update)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_uploads(*, session: Session, dataset: Dataset | DatasetPart) -> list[Upload]:
    if isinstance(dataset, DatasetPart):
        statement = select(Upload).where(
            Upload.dataset_parts.any(dataset_part_id=dataset.dataset_part_id)
        )
    else:
        statement = select(Upload).where(Upload.dataset == dataset)
    uploads = session.exec(statement).all()
    return uploads


def get_uploads_from_tag(*, session: Session, tag: str) -> list[Upload]:
    statement = select(Upload).join(Dataset).where(Dataset.tags.any(tag=tag))
    uploads = session.exec(statement).all()
    return uploads


def get_upload_from_short_hash(*, session: Session, short_hash: str) -> Optional[Upload]:
    statement = select(Upload).join(TorrentFile).filter(TorrentFile.short_hash == short_hash)
    upload = session.exec(statement).first()
    return upload


def get_upload_from_infohash(*, infohash: str, session: Session) -> Optional[Upload]:
    """
    Get a torrent from one of its infohashes.

    If the generic ``infohash`` is passed, it can be v1, v2, or the short hash.
    Otherwise, v1 and v2 can be passed, individually or together.
    """
    if len(infohash) == 8:
        return get_upload_from_short_hash(short_hash=infohash, session=session)
    elif len(infohash) == 40:
        statement = select(Upload).join(TorrentFile).filter(TorrentFile.v1_infohash == infohash)
    elif len(infohash) == 64:
        statement = select(Upload).join(TorrentFile).filter(TorrentFile.v2_infohash == infohash)
    else:
        raise ValueError("Infohash is not a short hash, v1, or v2 infohash")

    value = session.exec(statement).first()
    return value


def log_moderation_action(
    *,
    session: Session,
    actor: Account,
    action: ModerationAction,
    target: Dataset | Account | Upload,
    value: Optional[str] = None,
) -> AuditLog:
    audit_kwargs = {"actor": actor, "action": action, "value": value}

    if isinstance(target, Dataset):
        audit_kwargs["target_dataset"] = target
    elif isinstance(target, Upload):
        audit_kwargs["target_upload"] = target
    elif isinstance(target, Account):
        audit_kwargs["target_account"] = target
    else:
        raise ValueError(f"No moderation actions for target type {target}")

    db_item = AuditLog(**audit_kwargs)
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def check_existing_dataset_parts(
    *, session: Session, dataset: Dataset, part_slugs: list[str | DatasetPartCreate]
) -> Optional[list[str]]:
    """
    Check whether any of a list of dataset parts exist in the database,
    returning a list of slugs that do exist, if any.
    ``None`` otherwise.
    """
    slugs = [p if isinstance(p, str) else p.part_slug for p in part_slugs]
    stmt = (
        select(DatasetPart.part_slug)
        .join(Dataset)
        .filter(DatasetPart.dataset == dataset, DatasetPart.part_slug.in_(slugs))
    )
    existing_parts = session.exec(stmt).all()
    if not existing_parts:
        return None
    else:
        return existing_parts
