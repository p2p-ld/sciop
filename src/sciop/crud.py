from typing import Any, Literal, Optional

from sqlmodel import Session, select

from sciop.api.auth import get_password_hash, verify_password
from sciop.models import (
    Account,
    AccountCreate,
    AuditLog,
    Dataset,
    DatasetClaim,
    DatasetCreate,
    DatasetPart,
    DatasetPartCreate,
    DatasetPath,
    DatasetURL,
    ExternalIdentifier,
    FileInTorrent,
    ModerationAction,
    SiteStats,
    Tag,
    TorrentFile,
    TorrentFileCreate,
    TorrentTrackerLink,
    Tracker,
    TrackerCreate,
    Upload,
    UploadCreate,
    Webseed,
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
    *,
    session: Session,
    dataset_create: DatasetCreate,
    current_account: Optional[Account] = None,
    **kwargs: Any,
) -> Dataset:
    is_approved = current_account is not None and current_account.has_scope("submit")
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

    tags = get_tags(session=session, tags=dataset_create.tags)

    params = {
        "is_approved": is_approved,
        "account": current_account,
        "urls": urls,
        "tags": tags,
        "external_identifiers": external_identifiers,
        "parts": parts,
    }
    # update from kwargs - kwargs are overrides that should mostly be used in tests
    params.update(kwargs)

    db_obj = Dataset.model_validate(
        dataset_create,
        update=params,
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
    # check for existing part
    if dataset:
        existing = session.exec(
            select(DatasetPart).where(
                DatasetPart.part_slug == dataset_part.part_slug,
                DatasetPart.dataset_id == dataset.dataset_id,
            )
        ).first()
        if existing:
            return existing

    # create a new part!
    paths = [DatasetPath(path=str(path)) for path in dataset_part.paths]
    is_approved = bool(account) and account.has_scope("submit")
    part = DatasetPart.model_validate(
        dataset_part,
        update={
            "paths": paths,
            "dataset": dataset,
            "account": account,
            "is_approved": is_approved,
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
    statement = select(Dataset).where(Dataset.is_approved == True)
    return session.exec(statement).all()


def get_visible_dataset(
    *, session: Session, dataset_slug: str, account: Account | None = None
) -> Dataset | None:
    stmt = select(Dataset).where(Dataset.slug == dataset_slug, Dataset.visible_to(account) == True)
    return session.exec(stmt).first()


def get_visible_datasets(*, session: Session, account: Account | None = None) -> list[Dataset]:
    statement = select(Dataset).where(Dataset.visible_to(account) == True)
    return session.exec(statement).all()


def get_approved_datasets_from_tag(*, session: Session, tag: str) -> list[Upload]:
    statement = select(Dataset).where(Dataset.is_approved == True, Dataset.tags.any(tag=tag))
    return session.exec(statement).all()


def get_visible_datasets_from_tag(*, session: Session, tag: str) -> list[Dataset]:
    statement = select(Dataset).where(Dataset.is_visible == True, Dataset.tags.any(tag=tag))
    return session.exec(statement).all()


def get_review_datasets(*, session: Session) -> list[Dataset]:
    statement = select(Dataset).where(Dataset.needs_review == True)
    datasets = session.exec(statement).all()
    return datasets


def get_review_datasets_from_tag(*, session: Session, tag: str) -> list[Upload]:
    statement = select(Dataset).where(Dataset.needs_review == True, Dataset.tags.any(tag=tag))
    return session.exec(statement).all()


def get_review_uploads(*, session: Session) -> list[Upload]:
    statement = select(Upload).where(Upload.needs_review == True)
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
    existing_trackers = session.exec(
        select(Tracker).filter(Tracker.announce_url.in_(created_torrent.announce_urls))
    ).all()
    existing_tracker_str = set([e.announce_url for e in existing_trackers])
    new_tracker_urls = set(created_torrent.announce_urls) - existing_tracker_str
    new_trackers = []
    for url in new_tracker_urls:
        tracker = Tracker.model_validate(TrackerCreate(announce_url=url))
        session.add(tracker)
        new_trackers.append(tracker)

    # FIXME: this takes an extremely long time for no reason.
    files = [FileInTorrent(path=file.path, size=file.size) for file in created_torrent.files]
    if created_torrent.webseeds:
        webseeds = [
            Webseed(url=ws, status="in_original", account=account)
            for ws in created_torrent.webseeds
        ]
    else:
        webseeds = []
    db_obj = TorrentFile.model_validate(
        created_torrent, update={"files": files, "account": account, "webseeds": webseeds}
    )
    session.add(db_obj)

    # create link model entries
    links = []
    for tracker in (*existing_trackers, *new_trackers):
        link = TorrentTrackerLink(tracker=tracker, torrent=db_obj)
        session.add(link)
        links.append(link)

    session.commit()
    session.refresh(db_obj)
    return db_obj


def create_upload(
    *, session: Session, created_upload: UploadCreate, account: Account, dataset: Dataset
) -> Upload:
    """
    Create a new upload

    Clears any existing claims against the dataset or dataset parts
    """
    torrent = get_torrent_from_infohash(session=session, infohash=created_upload.infohash)
    update = {
        "torrent": torrent,
        "account": account,
        "dataset": dataset,
        "infohash": created_upload.infohash,
        "is_approved": account.has_scope("upload"),
    }
    if created_upload.part_slugs:
        update["dataset_parts"] = get_dataset_parts(
            session=session, dataset_slug=dataset.slug, dataset_part_slugs=created_upload.part_slugs
        )

    db_obj = Upload.model_validate(created_upload, update=update)
    db_obj.is_approved = account.has_scope("upload")
    session.add(db_obj)

    # clear outstanding claims, if any
    clear_claims(
        session=session,
        username=account.username,
        dataset_slug=dataset.slug,
        part_slugs=created_upload.part_slugs,
        commit=False,
    )

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


def get_visible_uploads(
    *, session: Session, dataset: Dataset | DatasetPart, account: Account | None = None
) -> list[Upload]:
    if isinstance(dataset, DatasetPart):
        statement = select(Upload).where(
            Upload.dataset_parts.any(dataset_part_id=dataset.dataset_part_id),
            Upload.visible_to(account=account) == True,
        )
    else:
        statement = select(Upload).where(
            Upload.dataset == dataset, Upload.visible_to(account=account) == True
        )
    uploads = session.exec(statement).all()
    return uploads


def get_uploads_from_tag(
    *, session: Session, tag: str, visible: Optional[bool] = True
) -> list[Upload]:
    if visible:
        statement = (
            select(Upload)
            .join(Dataset)
            .where(Dataset.tags.any(tag=tag), Upload.is_visible == visible)
            .order_by(Upload.created_at.desc())
        )
    else:
        statement = (
            select(Upload)
            .join(Dataset)
            .where(Dataset.tags.any(tag=tag))
            .order_by(Upload.created_at.desc())
        )
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
    elif isinstance(target, DatasetPart):
        audit_kwargs["target_dataset_part"] = target
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


def get_tag(*, session: Session, tag: str) -> Optional[Tag]:
    statement = select(Tag).where(Tag.tag == tag)
    tag = session.exec(statement).first()
    return tag


def get_tags(*, session: Session, tags: list[str], commit: bool = False) -> list[Tag]:
    """
    Given a list of tags as strings,
    get any existing tags and create non-existing ones, returning all.
    """
    existing_tags = session.exec(select(Tag).filter(Tag.tag.in_(tags))).all()
    existing_tag_str = set([e.tag for e in existing_tags])
    new_tags = set(tags) - existing_tag_str
    new_tags = [Tag(tag=tag) for tag in new_tags]
    if commit:
        for tag in new_tags:
            session.add(tag)
        session.commit()
        for tag in new_tags:
            session.refresh(tag)

    all_tags = [*existing_tags, *new_tags]
    return all_tags


def get_latest_site_stats(*, session: Session) -> SiteStats:
    return session.exec(select(SiteStats).order_by(SiteStats.created_at.desc()).limit(1)).first()


def get_claims(
    *,
    session: Session,
    username: str,
    dataset_slug: str,
    part_slugs: list[str] | Literal[True] | None = None,
) -> None | list[DatasetClaim]:
    """
    Get dataset claims for a dataset or its parts.
    If part_slugs is `None`, only return claims for the parent dataset.
    If part slugs is `True`, return all claims for all parts.
    """
    if part_slugs is None:
        maybe_claim = session.exec(
            select(DatasetClaim)
            .join(DatasetClaim.account)
            .where(
                Account.username == username,
                Dataset.slug == dataset_slug,
                DatasetClaim.dataset_part == None,  # noqa: E711
            )
        ).first()
        if maybe_claim:
            return [maybe_claim]
        else:
            return None
    elif part_slugs is True:
        return session.exec(
            select(DatasetClaim)
            .join(DatasetClaim.account)
            .where(Account.username == username, Dataset.slug == dataset_slug)
        ).all()
    else:
        if isinstance(part_slugs, str):
            part_slugs = [part_slugs]
        return session.exec(
            select(DatasetClaim)
            .join(DatasetClaim.account)
            .join(DatasetClaim.dataset_part)
            .where(
                Account.username == username,
                Dataset.slug == dataset_slug,
                DatasetPart.part_slug.in_(part_slugs),
            )
        ).all()


def clear_claims(
    *,
    session: Session,
    username: str,
    dataset_slug: str,
    part_slugs: list[str] | Literal[True] | None = None,
    commit: bool = True,
) -> None:
    """
    Clear all claims for a dataset or set of dataset parts
        If part_slugs is `None`, only clear claims for the parent dataset.
    If part slugs is `True`, clear all claims for all parts.
    """
    claims = get_claims(
        session=session, username=username, dataset_slug=dataset_slug, part_slugs=part_slugs
    )
    if claims:
        for claim in claims:
            session.delete(claim)
    if commit:
        session.commit()
