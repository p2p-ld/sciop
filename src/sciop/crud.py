from typing import Optional

from sqlmodel import Session, select

from sciop.api.auth import get_password_hash, verify_password
from sciop.models import (
    Account,
    AccountCreate,
    AuditLog,
    Dataset,
    DatasetCreate,
    Upload,
    UploadCreate,
    DatasetTag,
    DatasetURL,
    FileInTorrent,
    ModerationAction,
    TorrentFile,
    TorrentFileCreate,
    TrackerInTorrent,
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
    enabled = current_account is not None and any(
        [scope.name == "submit" for scope in current_account.scopes]
    )
    urls = [DatasetURL(url=url) for url in dataset_create.urls]
    tags = [DatasetTag(tag=tag) for tag in dataset_create.tags]

    db_obj = Dataset.model_validate(
        dataset_create,
        update={"enabled": enabled, "account": current_account, "urls": urls, "tags": tags},
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_dataset(*, session: Session, dataset_slug: str) -> Dataset | None:
    """Get a dataset by its slug"""
    statement = select(Dataset).where(Dataset.slug == dataset_slug)
    session_dataset = session.exec(statement).first()
    return session_dataset


def get_approved_datasets(*, session: Session) -> list[Dataset]:
    statement = select(Dataset).where(Dataset.enabled == True)
    return session.exec(statement).all()


def get_review_datasets(*, session: Session) -> list[Dataset]:
    statement = select(Dataset).where(Dataset.enabled == False)
    datasets = session.exec(statement).all()
    return datasets


def get_review_uploads(*, session: Session) -> list[Upload]:
    statement = select(Upload).where(Upload.enabled == False)
    uploads = session.exec(statement).all()
    return uploads


def get_torrent_from_hash(*, hash: str, session: Session) -> Optional[TorrentFile]:
    statement = select(TorrentFile).where(TorrentFile.hash == hash)
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
    torrent = get_torrent_from_short_hash(
        session=session, short_hash=created_upload.torrent_short_hash
    )
    db_obj = Upload.model_validate(
        created_upload,
        update={
            "torrent": torrent,
            "account": account,
            "dataset": dataset,
            "short_hash": created_upload.torrent_short_hash,
        },
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_uploads(*, dataset: Dataset, session: Session) -> list[Upload]:
    statement = select(Upload).where(Upload.dataset == dataset)
    uploads = session.exec(statement).all()
    return uploads


def get_uploads_from_tag(*, session: Session, tag: str) -> list[Upload]:
    statement = select(Upload).join(Dataset).join(DatasetTag).filter(DatasetTag.tag == tag)
    uploads = session.exec(statement).all()
    return uploads


def get_upload_from_short_hash(*, session: Session, short_hash: str) -> Optional[Upload]:
    statement = select(Upload).join(TorrentFile).filter(TorrentFile.short_hash == short_hash)
    upload = session.exec(statement).first()
    return upload


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
