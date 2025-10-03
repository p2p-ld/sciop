import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Optional, Self, Union, cast

from annotated_types import MaxLen
from pydantic import BaseModel, TypeAdapter, computed_field, field_validator, model_validator
from sqlalchemy import SQLColumnExpression, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.attributes import AttributeEventToken
from sqlalchemy.schema import UniqueConstraint
from sqlmodel import Field, Relationship, select
from sqlmodel.main import FieldInfo

from sciop.const import DATASET_PART_RESERVED_SLUGS, DATASET_RESERVED_SLUGS, PREFIX_LEN
from sciop.models.account import Account, AccountDatasetScopeLink
from sciop.models.base import SQLModel
from sciop.models.mixins import (
    EditableMixin,
    FrontendMixin,
    ListlikeMixin,
    ModerableMixin,
    SearchableMixin,
    SortableCol,
    SortMixin,
    TableMixin,
    TableReadMixin,
    all_optional,
    exclude_fields,
)
from sciop.models.scope import ItemScopesRead
from sciop.models.tag import DatasetTagLink
from sciop.services.markdown import render_db_fields_to_html
from sciop.types import (
    AccessType,
    EscapedStr,
    ExternalIdentifierType,
    IDField,
    InputType,
    MaxLenURL,
    PathLike,
    Scarcity,
    ScrapeStatus,
    SlugStr,
    SourceType,
    Threat,
    UsernameStr,
    UTCDateTime,
)

if TYPE_CHECKING:
    from sqlmodel import Session

    from sciop.models import AuditLog, DatasetClaim, Report, Tag, Upload, UploadRead

PREFIX_PATTERN = re.compile(r"\w{6}-[A-Z]{3}_\S+")


def _prefixed_len(info: FieldInfo) -> int:
    max_len = [md for md in info.metadata if isinstance(md, MaxLen)][0]
    return max_len.max_length + PREFIX_LEN


class DatasetBase(ModerableMixin, FrontendMixin):
    __name__: ClassVar[str] = "dataset"

    title: str = Field(
        title="Title",
        description="""
    Human readable name for dataset. 
    Match the title given by the source as closely as possible.
    """,
        min_length=3,
        max_length=512,
        schema_extra={"json_schema_extra": {"input_type": InputType.input}},
    )
    slug: SlugStr = Field(
        title="Dataset Slug",
        description="""
    Short, computer readable identifier for dataset.
    The acronym or abbreviation of the dataset name, e.g. for the NOAA
    "Fundamental Climate Data Record - Mean Layer Temperature NOAA"
    use "fcdr-mlt-noaa". Converted to a slugified string.
    """,
        min_length=2,
        max_length=128,
        schema_extra={"json_schema_extra": {"input_type": InputType.input}},
    )
    publisher: str = Field(
        title="Publisher",
        description="""
    The agency, organization, author, group, publisher, etc. that is associated with the dataset.
    Please use a canonical acronym/abbreviation form of the name when possible,
    using the autocompleted values if any correct matches are listed.
    """,
        max_length=256,
        schema_extra={
            "json_schema_extra": {"autocomplete": "publisher", "input_type": InputType.input}
        },
    )
    homepage: Optional[MaxLenURL] = Field(
        None,
        title="Homepage",
        description="""
    The index/landing page that describes this dataset, if any. 
    If the dataset has multiple associated URLs, if e.g. an index page with metadata
    is different from the download URL, add ths index here and additional URLs below.
    """,
        schema_extra={"json_schema_extra": {"input_type": InputType.input}},
    )
    description: Optional[str] = Field(
        None,
        title="Description",
        description="""
    Additional information about the dataset. Markdown input is supported.
    """,
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
        max_length=163840,
    )
    description_html: Optional[str] = Field(
        default="",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
        max_length=655360,
    )
    dataset_created_at: Optional[UTCDateTime] = Field(
        None,
        title="Dataset Creation Date",
        description="""
        Datetime when dataset was originally created in UTC. May be approximate or left blank.
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.input}},
    )
    dataset_updated_at: Optional[UTCDateTime] = Field(
        None,
        title="Dataset Last Updated",
        description="""
        Datetime when the dataset was last updated in UTC. May be approximate or left blank
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.input}},
    )
    source_type: SourceType = Field(
        "unknown",
        title="Source Type",
        description="""
    The protocol/technology needed to download the dataset.
    Use "web" if the dataset is an archive of websites themselves,
    and "http" if the dataset is some other raw data available via http download.
    """,
        schema_extra={"json_schema_extra": {"input_type": InputType.select}},
    )
    source_available: bool = Field(
        default=True,
        title="Source Available",
        description="""
        Whether the canonical source of this dataset is still available.
        Default true unless known to be taken down.
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.input}},
    )
    last_seen_at: Optional[UTCDateTime] = Field(
        default=None,
        title="Last Seen At",
        description="""
        If the dataset has been removed, the last time it was known to be available. 
        If the dataset is scheduled to be removed, 
        the time in the future where it is expected to be unavailable. 
        Otherwise, leave blank.
        Times should be in UTC.
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.input}},
    )
    source_access: AccessType = Field(
        default="unknown",
        title="Source Access",
        description="""
    How the canonical source can be accessed, whether it needs credentials
    or is intended to be public.
    """,
        schema_extra={"json_schema_extra": {"input_type": InputType.select}},
    )
    scarcity: Scarcity = Field(
        default="unknown",
        title="Scarcity",
        description="""
    To prioritize scrapes, an estimate of the rarity of this dataset.
    Datasets that are likely to only exist in one or a few places are prioritized over
    those that are widely available.
    """,
        schema_extra={"json_schema_extra": {"input_type": InputType.select}},
    )
    threat: Threat = Field(
        default="unknown",
        title="Threat",
        description="""
    To prioritize scrapes, an estimate of how likely this dataset is likely to disappear
    in the immediate future. Datasets that are under direct threat due to the their nature
    or specific threats made against them are prioritized over those 
    for whom no specific threat exists.
    """,
        schema_extra={"json_schema_extra": {"input_type": InputType.select}},
    )

    @property
    def frontend_url(self) -> str:
        return f"/datasets/{self.slug}/"

    @hybrid_property
    def short_name(self) -> str:
        return self.slug


class Dataset(DatasetBase, TableMixin, SearchableMixin, EditableMixin, SortMixin, table=True):
    __tablename__ = "datasets"
    __searchable__ = {
        "title": 5.0,
        "slug": 1.0,
        "publisher": 2.0,
        "homepage": 1.0,
        "description": 3.0,
    }
    __sortable__ = (
        SortableCol(),
        SortableCol(name="slug", title="slug"),
        SortableCol(name="title", title="title"),
        SortableCol(
            name="threat",
            title="""
        <span class="dataset-threat threat-dot threat-extinct"></span>
        """,
            tooltip="Sort by threat category of the dataset",
        ),
        SortableCol(name="created_at", title="created"),
    )
    __table_args__ = (UniqueConstraint("slug", name="uq_datasets_slug"),)

    created_at: Optional[UTCDateTime] = Field(default_factory=lambda: datetime.now(UTC), index=True)
    slug: SlugStr = Field(
        unique=True,
        index=True,
        min_length=2,
        max_length=_prefixed_len(DatasetBase.model_fields["slug"]),
    )
    dataset_id: IDField = Field(None, primary_key=True)
    uploads: list["Upload"] = Relationship(back_populates="dataset")
    external_sources: list["ExternalSource"] = Relationship(back_populates="dataset")
    external_identifiers: list["ExternalIdentifier"] = Relationship(back_populates="dataset")
    urls: list["DatasetURL"] = Relationship(back_populates="dataset")
    tags: list["Tag"] = Relationship(
        back_populates="datasets",
        sa_relationship_kwargs={"lazy": "selectin"},
        link_model=DatasetTagLink,
    )
    account_id: Optional[int] = Field(default=None, foreign_key="accounts.account_id", index=True)
    account: Optional["Account"] = Relationship(back_populates="datasets")
    account_scopes: list["AccountDatasetScopeLink"] = Relationship(back_populates="dataset")
    scrape_status: ScrapeStatus = "unknown"
    audit_log_target: list["AuditLog"] = Relationship(back_populates="target_dataset")
    reports: list["Report"] = Relationship(back_populates="target_dataset")
    parts: list["DatasetPart"] = Relationship(back_populates="dataset")
    claims: list["DatasetClaim"] = Relationship(back_populates="dataset")

    def update(self, session: "Session", new: "DatasetUpdate", commit: bool = False) -> "Dataset":
        from sciop import crud

        updated = new.model_dump(exclude_unset=True)
        if "tags" in updated:
            updated["tags"] = crud.get_tags(session=session, tags=updated["tags"])
        if "urls" in updated:
            updated["urls"] = DatasetURL.get_items(self.urls, updated["urls"])
        if "external_identifiers" in updated:
            updated["external_identifiers"] = ExternalIdentifier.get_items(
                self.external_identifiers, updated["external_identifiers"]
            )
        if "account_scopes" in updated:
            updated["account_scopes"] = crud.get_account_item_scopes(
                session=session,
                account_scopes=[
                    ItemScopesRead(username=scope["username"], scopes=scope["scopes"])
                    for scope in updated["account_scopes"]
                    if "scopes" in scope
                ],
                existing_scopes=self.account_scopes,
            )

        for field_name, new_value in updated.items():
            setattr(self, field_name, new_value)

        if commit:
            session.add(self)
            session.commit()
            session.refresh(self)
        return self

    def to_read(self) -> "DatasetRead":
        return DatasetRead.model_validate(self)


event.listen(Dataset, "before_update", render_db_fields_to_html("description"))
event.listen(Dataset, "before_insert", render_db_fields_to_html("description"))


@event.listens_for(Dataset.is_removed, "set")
def _datset_prefix_on_removal(
    target: Dataset, value: bool, oldvalue: bool, initiator: AttributeEventToken
) -> None:
    """Add or remove a prefix when removal state is toggled"""
    if value:
        # add prefix
        target.slug = Dataset._add_prefix(target.slug, target.created_at, "REM")
    else:
        target.slug = Dataset._remove_prefix(target.slug)


class DatasetCreate(DatasetBase):
    urls: list[MaxLenURL] = Field(
        default_factory=list,
        title="URL(s)",
        description="""
        URL(s) to the direct download of the data, if public, 
        or any additional URLs associated with the dataset.
        One URL per line.
        If uploading a recursive web archive dump, only the top-level URL is needed.
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
        max_length=512,
    )
    tags: list[Annotated[SlugStr, Field(min_length=2, max_length=32)]] = Field(
        title="Tags",
        description="""
        Tags for this dataset. Use matching autocomplete values, when available.
        Enter as comma separated list or press enter to store a token.
        Only lowercase alphanumeric characters and `-` are allowed.
        Include as many tags as are applicable: topic, data type/file type,
        if this dataset is part of a collection (e.g. each dataset in NOAA's
        Fundamental Climate Data Records should be tagged with `fcdr`), etc.
        Tags are used to generate RSS feeds so people can reseed data that is important to them.
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.tokens}},
        min_length=1,
        max_length=512,
    )
    account_scopes: Optional[list["ItemScopesRead"]] = Field(
        title="Collaborators",
        description="""
        Additional users who should be able to make changes to this dataset.
        Supply a username and press enter to start granting them permissions.
        Hover over permission buttons to see their descriptions.
        """,
        schema_extra={"json_schema_extra": {"input_type": InputType.account_scopes}},
        max_length=512,
        default=[],
    )
    external_identifiers: list["ExternalIdentifierCreate"] = Field(
        title="External Identifiers",
        default_factory=list,
        schema_extra={
            "json_schema_extra": {
                "input_type": InputType.model_list,
                "model_name": "ExternalIdentifierCreate",
            }
        },
        max_length=32,
    )
    parts: list["DatasetPartCreate"] = Field(
        default_factory=list,
        title="Part(s)",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
    )

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> Self:
        """Reverse a dataset into its creation form, e.g. for editing :)"""
        return cls.model_validate(
            dataset,
            update={
                "urls": [url.url for url in dataset.urls],
                "tags": [tag.tag for tag in dataset.tags],
                "external_identifiers": [
                    ExternalIdentifierCreate.model_validate(ex)
                    for ex in dataset.external_identifiers
                ],
                "account_scopes": [
                    ItemScopesRead(
                        username=username,
                        scopes=[
                            s.scope.value
                            for s in dataset.account_scopes
                            if s.account.username == username
                        ],
                    )
                    for username in list(
                        dict.fromkeys([s.account.username for s in dataset.account_scopes])
                    )
                ],
                "parts": [DatasetPartCreate.model_validate(part) for part in dataset.parts],
            },
        )

    @field_validator("urls", "tags", mode="before")
    def split_lines(cls, value: str | list[str]) -> Optional[list[str]]:
        """Split lists of strings given as one entry per line"""
        return _split_lines(value)

    @field_validator("tags", "tags", mode="before")
    def split_commas(cls, value: str | list[str]) -> Optional[list[str]]:
        """Split lists of strings given as one entry per line"""
        if isinstance(value, str):
            if not value or value == "":
                return None
            value = value.split(",")
        elif value is None:
            return None

        # split any substrings, e.g. if comma-separated strings are used in
        # the token-input style of tag entry
        split_val = []
        for v in value:
            split_subvals = v.split(",")
            split_subvals = [subv.strip() for subv in split_subvals]
            split_val.extend(split_subvals)
        value = split_val

        # filter empty strings
        value = [v for v in value if v.strip()]

        # if left with an empty list, None
        if value:
            return value
        else:
            return None

    @field_validator("*", mode="before")
    def empty_strings_are_none(cls, value: Any) -> Any:
        """Forms sometimes submit input without anything as empty strings not None"""
        if value == "":
            value = None
        return value

    @field_validator("slug", mode="after")
    def not_reserved_slug(cls, slug: str) -> str:
        assert slug not in DATASET_RESERVED_SLUGS, f"slug {slug} is reserved"
        return slug


@exclude_fields("parts")
@all_optional
class DatasetUpdate(DatasetCreate):
    """
    Version of dataset creation where all fields are optional
    and we don't try and update the entire database in one call
    (by excluding related items, except when they are strictly subordinate
    to this object instance (like external identifiers) or scalar (tags))
    """


class DatasetRead(DatasetBase, TableReadMixin):
    slug: SlugStr = Field(min_length=2, max_length=_prefixed_len(DatasetBase.model_fields["slug"]))
    uploads: list["UploadRead"] = Field(default_factory=list)
    external_sources: list["ExternalSource"] = Field(default_factory=list)
    external_identifiers: list["ExternalIdentifierRead"] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    scrape_status: ScrapeStatus
    is_approved: bool

    @field_validator("tags", mode="before")
    def collapse_tags(cls, val: list["Tag"]) -> list[str]:
        return [tag.tag for tag in val]

    @field_validator("urls", mode="before")
    def collapse_urls(cls, val: list["DatasetURL"]) -> list[str]:
        return [url.url for url in val]

    @field_validator("tags", mode="after")
    def sort_list(cls, val: list[Any]) -> list[Any]:
        return sorted(val)


class DatasetURL(EditableMixin, ListlikeMixin, table=True):
    __tablename__ = "dataset_urls"
    __value_column_name__ = "url"

    dataset_url_id: IDField = Field(default=None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="datasets.dataset_id", index=True)
    dataset: Optional[Dataset] = Relationship(back_populates="urls")

    url: MaxLenURL


class ExternalSourceBase(SQLModel):
    """An external source for this dataset"""

    source: EscapedStr = Field(
        description="The name of the group or person who provides the dataset",
        max_length=256,
    )
    url: MaxLenURL = Field(description="Link to the external source", max_length=512)
    description: str = Field(
        description="Additional information about the completeness, accuracy, etc. "
        "of the external source",
        max_length=4096,
    )


class ExternalSource(ExternalSourceBase, TableMixin, EditableMixin, table=True):
    __tablename__ = "external_sources"

    external_source_id: IDField = Field(None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="datasets.dataset_id", index=True)
    dataset: Dataset = Relationship(back_populates="external_sources")
    account_id: Optional[int] = Field(default=None, foreign_key="accounts.account_id", index=True)
    account: Optional[Account] = Relationship(back_populates="external_submissions")


class ExternalIdentifierBase(SQLModel):
    """
    Some additional, probably persistent identifier for a dataset
    """

    type: ExternalIdentifierType
    identifier: str = Field(min_length=1, max_length=512)

    @property
    def uri(self) -> str:
        if self.type in ("ark"):
            return f"{self.type}:{self.identifier}"
        elif self.type == "cid":
            return f"https://dweb.link/ipfs/{self.identifier}"
        elif self.type == "doi":
            return f"https://doi.org/{self.identifier}"
        elif self.type == "isni":
            return f"https://isni.org/isni/{self.identifier}"
        elif self.type == "issn":
            return f"https://urn.issn.org/urn:issn:{self.identifier}"
        elif self.type == "isbn":
            return f"urn:{self.type}:{self.identifier}"
        elif self.type in ("purl", "urn", "uri"):
            return self.identifier


class ExternalIdentifier(
    ExternalIdentifierBase, TableMixin, EditableMixin, ListlikeMixin, table=True
):
    __tablename__ = "external_identifiers"
    __value_column_name__ = ("type", "identifier")

    external_identifier_id: IDField = Field(None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="datasets.dataset_id", index=True)
    dataset: Dataset = Relationship(back_populates="external_identifiers")


class ExternalIdentifierCreate(ExternalIdentifierBase):
    @field_validator("identifier", mode="before")
    def strip_whitespace(cls, val: str) -> str:
        return val.strip()

    @model_validator(mode="after")
    def validate_by_type(self) -> Self:
        """
        Apply additional validation from the annotation on the external identifier type
        """
        annotation = ExternalIdentifierType.__annotations__.get(self.type, None)
        if annotation is None:
            return self

        adapter = TypeAdapter(annotation)
        self.identifier = adapter.validate_python(self.identifier)
        return self


class ExternalIdentifierRead(ExternalIdentifierBase):
    pass


class UploadDatasetPartLink(SQLModel, table=True):
    __tablename__ = "upload_dataset_part_links"
    dataset_part_id: Optional[int] = Field(
        default=None, foreign_key="dataset_parts.dataset_part_id", primary_key=True, index=True
    )
    upload_id: Optional[int] = Field(
        default=None, foreign_key="uploads.upload_id", primary_key=True, index=True
    )


class DatasetPartBase(SQLModel, FrontendMixin):
    __name__: ClassVar[str] = "dataset part"

    part_slug: SlugStr = Field(
        title="Part Slug",
        description="Unique identifier for this dataset part",
        min_length=1,
        max_length=256,
        schema_extra={"json_schema_extra": {"input_type": InputType.input}},
    )
    description: Optional[str] = Field(
        None,
        title="Description",
        description="Additional information about this part. Markdown input is supported.",
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
        max_length=4096,
    )
    description_html: Optional[str] = Field(
        "",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
        max_length=8192,
    )

    @property
    def frontend_url(self) -> str:
        return f"/datasets/{self.dataset.slug}/{self.part_slug}/"

    @hybrid_property
    def short_name(self) -> str:
        return self.dataset.slug + "/" + self.part_slug

    @short_name.inplace.expression
    @classmethod
    def _short_name(cls) -> SQLColumnExpression[str]:
        return (
            select(Dataset.slug + "/" + DatasetPart.part_slug)
            .join(Dataset.parts)
            .where(Dataset.dataset_id == cls.dataset_id)
            .label("short_name")
        )

    @property
    def link_to(self) -> str:
        """A rendered <a> element linking to the item"""
        return (
            f"<span>"
            f'  {self.dataset.link_to}/<a href="{self.frontend_url}">{self.part_slug}</a>'
            f"</span>"
        )


class DatasetPart(DatasetPartBase, TableMixin, ModerableMixin, EditableMixin, table=True):
    __tablename__ = "dataset_parts"
    __table_args__ = (UniqueConstraint("dataset_id", "part_slug", name="_dataset_part_slug_uc"),)

    part_slug: SlugStr = Field(
        index=True,
        min_length=1,
        max_length=_prefixed_len(DatasetPartBase.model_fields["part_slug"]),
    )
    dataset_part_id: IDField = Field(None, primary_key=True)
    dataset_id: Optional[int] = Field(None, foreign_key="datasets.dataset_id", index=True)
    dataset: Optional[Dataset] = Relationship(back_populates="parts")
    account_id: Optional[int] = Field(None, foreign_key="accounts.account_id", index=True)
    account: Optional[Account] = Relationship(back_populates="dataset_parts")
    uploads: list["Upload"] = Relationship(
        back_populates="dataset_parts", link_model=UploadDatasetPartLink
    )
    paths: list["DatasetPath"] = Relationship(back_populates="dataset_part")
    audit_log_target: list["AuditLog"] = Relationship(back_populates="target_dataset_part")
    reports: list["Report"] = Relationship(back_populates="target_dataset_part")
    claims: list["DatasetClaim"] = Relationship(back_populates="dataset_part")

    def update(
        self, session: "Session", new: "DatasetPartUpdate", commit: bool = False
    ) -> "DatasetPart":
        updated = new.model_dump(exclude_unset=True)
        if "paths" in updated:
            updated["paths"] = DatasetPath.get_items(self.paths, updated["paths"])
        for key, value in updated.items():
            setattr(self, key, value)
        if commit:
            session.add(self)
            session.commit()
            session.refresh(self)
        return self

    def to_read(self) -> "DatasetPartRead":
        return DatasetPartRead.model_validate(self)


@event.listens_for(DatasetPart.is_removed, "set")
def _part_prefix_on_removal(
    target: DatasetPart, value: bool, oldvalue: bool, initiator: AttributeEventToken
) -> None:
    """Add or remove a prefix when removal state is toggled"""
    if value:
        # add prefix
        target.part_slug = DatasetPart._add_prefix(target.part_slug, target.created_at, "REM")
    else:
        target.part_slug = DatasetPart._remove_prefix(target.part_slug)


event.listen(DatasetPart, "before_update", render_db_fields_to_html("description"))
event.listen(DatasetPart, "before_insert", render_db_fields_to_html("description"))


class DatasetPartCreate(DatasetPartBase):
    paths: list[PathLike] = Field(
        default_factory=list,
        title="Paths",
        description="A list of paths that this part should contain, "
        "if the part is not a single file. One path per line.",
        max_length=2048,
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
    )

    @field_validator("paths", mode="before")
    def split_lines(cls, value: str | list[str]) -> Optional[list[str]]:
        return _split_lines(value)

    @field_validator("paths", mode="before")
    def unpack_dataset_path(cls, value: list[str] | list["DatasetPath"]) -> list[PathLike]:
        if not value:
            return value
        if isinstance(value[0], DatasetPath):
            value = cast(list[DatasetPath], value)
            value = [v.path for v in value]
        return value

    @field_validator("part_slug", mode="after")
    def not_reserved_slug(cls, slug: str) -> str:
        assert slug not in DATASET_PART_RESERVED_SLUGS, f"slug {slug} is reserved"
        return slug


@all_optional
class DatasetPartUpdate(DatasetPartCreate):
    pass


class DatasetPartRead(DatasetPartBase):
    dataset: DatasetRead
    uploads: list["UploadRead"] = Field(default_factory=list)
    account: UsernameStr

    @computed_field
    def absolute_slug(self) -> str:
        """Slug joined by / with the parent dataset slug"""
        return "/".join([self.dataset.slug, self.part_slug])

    @field_validator("account", mode="before")
    def account_to_username(cls, account: Union["Account", str]) -> str:
        from sciop.models import Account

        if isinstance(account, Account):
            account = account.username
        return account


class DatasetPath(TableMixin, ListlikeMixin, EditableMixin, table=True):
    __tablename__ = "dataset_paths"
    __value_column_name__ = "path"

    dataset_path_id: IDField = Field(None, primary_key=True)
    dataset_part_id: Optional[int] = Field(
        None, foreign_key="dataset_parts.dataset_part_id", index=True
    )
    dataset_part: DatasetPart = Relationship(back_populates="paths")
    path: str = Field(max_length=1024)


def _split_lines(value: str | list[str] | BaseModel) -> Optional[list[str] | BaseModel]:
    if isinstance(value, str):
        if not value or value == "":
            return []
        value = value.splitlines()
    elif isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], str):
            if "\n" in value[0]:
                value = value[0].splitlines()
            elif value[0] == "":
                return []
        elif len(value) == 0:
            return value
        elif isinstance(value[0], SQLModel):
            return value
    elif value is None:
        return []
    elif isinstance(value, SQLModel):
        # models aren't raw string input!
        return value

    # filter empty strings
    value = [v for v in value if v and v.strip()]
    return value
