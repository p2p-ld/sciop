from collections import defaultdict
from enum import StrEnum
from typing import Optional

import pytest
from sqlmodel import Field, Session, select

from sciop.models import (
    ItemScopeLink,
    Dataset,
    DatasetPart,
    DatasetTagLink,
    DatasetURL,
    Scope,
    Tag,
)
from sciop.models.mixins import SearchableMixin
from sciop.models.mixins.enum import EnumTableMixin


@pytest.mark.parametrize("reindex", [True, False])
def test_full_text_search(session, reindex: bool):
    """
    Weak test for whether full text search merely works.
    """

    match_ok = Dataset(
        title="Unrelated title that doesn't match but its description does",
        description="Matches a single thing once like key",
        slug="matching-ok",
        publisher="Agency of matching ok",
    )
    match_good = Dataset(
        title="Unrelated title that doesn't match but its description does even better",
        description="Matches several keywords like key and word several times, see key key key",
        slug="matching-good",
        publisher="Agency of matching good",
    )
    match_better = Dataset(
        title="Matches with title containing key",
        description="Matches two times key key ",
        slug="matching-better",
        publisher="Agency of matching better",
    )
    no_match = Dataset(
        title="Nothing in here",
        slug="not-good",
        publisher="Agency of not good",
    )

    session.add(match_ok)
    session.add(match_good)
    session.add(match_better)
    session.add(no_match)
    session.commit()

    if reindex:
        from sciop.db import get_engine

        engine = get_engine()
        for subcls in SearchableMixin.__subclasses__():
            subcls.fts_rebuild(engine)

    stmt = Dataset.search("key")
    results = session.execute(stmt).fetchall()

    assert len(results) == 3
    assert results[0].Dataset.slug == match_better.slug
    assert results[1].Dataset.slug == match_good.slug
    assert results[2].Dataset.slug == match_ok.slug


def test_full_text_search_mixed_order(session):
    """
    We should still find matches when the query is out of order compared to the source text
    """

    match_good = Dataset(
        title="Title matches a long out of order search query",
        description="Description matches lots of words in it, and matches a long search query. ",
        slug="matching-good",
        publisher="Agency of matching ok",
    )
    match_ok = Dataset(
        title="Sort of medium good matches",
        description="Description matches a long query sort of ok I suppose. "
        "it says order of and out",
        slug="matching-ok",
        publisher="Agency of matching good",
    )
    no_match = Dataset(
        title="Nothing in here",
        description="Nothing at all, no sir" * 100,
        slug="not-good",
        publisher="Agency of not good",
    )

    session.add(match_ok)
    session.add(match_good)
    session.add(no_match)
    session.commit()

    stmt = Dataset.search("long order out of query match")
    results = session.execute(stmt).fetchall()

    assert len(results) == 2
    assert results[0].Dataset.slug == match_good.slug
    assert results[1].Dataset.slug == match_ok.slug


def test_full_text_search_filter(session):
    """
    Full text search with an additional "where" query
    """
    matches = Dataset(
        title="Matches something",
        description="Has matches in it",
        slug="matching",
        publisher="Matching",
        is_approved=True,
    )
    matches_not_visible = Dataset(
        title="Matches something",
        description="Has matches in it",
        slug="matching-invisible",
        publisher="Matching",
        is_approved=False,
    )
    no_match = Dataset(
        title="Nothing",
        description="nothing, still visible tho",
        slug="nothing",
        publisher="Nothing",
        is_approved=True,
    )
    session.add(matches)
    session.add(matches_not_visible)
    session.add(no_match)
    session.commit()

    stmt = Dataset.search("match").where(Dataset.is_visible == True)
    results = session.execute(stmt).fetchall()
    assert len(results) == 1
    assert results[0].Dataset.slug == matches.slug


def test_search_editing(session):
    """
    Search index updates when items are updated
    """
    ds = Dataset(
        title="Nothing",
        description="Initially bad, but then good",
        slug="nothing",
        publisher="Nothing",
    )
    session.add(ds)
    session.commit()
    session.refresh(ds)
    stmt = Dataset.search("matches something")
    results = session.execute(stmt).fetchall()
    assert len(results) == 0

    ds.title = "Matches something now"
    ds.description = "the item matches something now"
    session.add(ds)
    session.commit()

    stmt = Dataset.search("matches something")
    results = session.execute(stmt).fetchall()
    assert len(results) == 1


def test_search_spicy_characters(session):
    """
    We can search with non-alphabetic characters
    """
    match1 = Dataset(
        title="It's in the slug",
        description="the sluuuuuggggg",
        slug="match-1",
        publisher="Nothing",
    )
    match2 = Dataset(
        title="Still in the slug",
        description="",
        slug="match-1-2",
        publisher="Nothing",
    )
    session.add(match1)
    session.add(match2)
    session.commit()
    session.refresh(match1)
    session.refresh(match2)

    stmt = Dataset.search("match-1")
    results = session.execute(stmt).fetchall()
    assert len(results) == 2


def test_ensure_enum(recreate_models):
    """
    ensure_enum creates all values from an enum
    """

    class MyEnum(StrEnum):
        head = "head"
        shoulders = "shoulders"
        knees = "knees"
        toes = "toes"

    class MyEnumTable(EnumTableMixin, table=True):
        __enum_column_name__ = "an_enum"
        table_id: Optional[int] = Field(default=None, primary_key=True)
        an_enum: MyEnum

    engine = recreate_models()

    with Session(engine) as session:
        MyEnumTable.ensure_enum_values(session)

        enum_rows = session.exec(select(MyEnumTable)).all()

    assert len(enum_rows) == len(MyEnum.__members__)
    row_vals = [row.an_enum for row in enum_rows]
    for item in MyEnum.__members__.values():
        assert item in row_vals


@pytest.mark.parametrize("is_approved", [True, False])
@pytest.mark.parametrize("is_removed", [True, False])
def test_visible_to(dataset, account, is_approved, is_removed, session):
    """
    Moderable items should be visible to users with dataset scopes and moderators if not removed,
    excluding the dataset creator if they have no scopes, even if not yet approved
    """
    creator = account(username="creator")
    permissioned = account(username="permissioned")
    public = account(username="public")
    reviewer = account(username="reviewer", scopes=["review"])
    moderable = dataset()
    moderable.account = creator
    moderable.scopes = [
        ItemScopeLink(
            account=permissioned, dataset=moderable, _scope=Scope.get_item("edit", session)
        )
    ]
    moderable.is_approved = is_approved
    moderable.is_removed = is_removed
    session.add(moderable)
    session.commit()
    session.refresh(moderable)

    if is_removed:
        assert not moderable.visible_to()
        assert not moderable.visible_to(public)
        assert not moderable.visible_to(creator)
        assert not moderable.visible_to(permissioned)
        assert not moderable.visible_to(reviewer)
    elif is_approved:
        assert moderable.visible_to()
        assert moderable.visible_to(public)
        assert moderable.visible_to(permissioned)
        assert moderable.visible_to(creator)
        assert moderable.visible_to(reviewer)
    else:
        assert not moderable.visible_to()
        assert not moderable.visible_to(public)
        assert not moderable.visible_to(creator)
        assert moderable.visible_to(permissioned)
        assert moderable.visible_to(reviewer)


@pytest.mark.parametrize("is_approved", [True, False])
@pytest.mark.parametrize("is_removed", [True, False])
def test_visible_to_expression(dataset, account, is_approved, is_removed, session):
    """
    Moderable items should be visible to to users with dataset scopes and moderators if not removed,
    excluding the dataset creator if they have no scopes,
    even if not yet approved when used as an expression
    """
    creator = account(username="creator")
    permissioned = account(username="permissioned")
    public = account(username="public")
    reviewer = account(username="reviewer", scopes=["review"])
    moderable = dataset()
    moderable.account = creator
    moderable.scopes = [
        ItemScopeLink(
            account=permissioned, dataset=moderable, _scope=Scope.get_item("edit", session)
        )
    ]
    moderable.is_approved = is_approved
    moderable.is_removed = is_removed
    session.add(moderable)
    session.commit()
    session.refresh(moderable)

    if is_removed:
        assert moderable not in session.exec(select(Dataset).where(Dataset.visible_to())).all()
        assert (
            moderable not in session.exec(select(Dataset).where(Dataset.visible_to(public))).all()
        )
        assert (
            moderable not in session.exec(select(Dataset).where(Dataset.visible_to(creator))).all()
        )
        assert (
            moderable not in session.exec(select(Dataset).where(Dataset.visible_to(reviewer))).all()
        )
        assert (
            moderable
            not in session.exec(select(Dataset).where(Dataset.visible_to(permissioned))).all()
        )
    elif is_approved:
        assert moderable in session.exec(select(Dataset).where(Dataset.visible_to())).all()
        assert moderable in session.exec(select(Dataset).where(Dataset.visible_to(public))).all()
        assert moderable in session.exec(select(Dataset).where(Dataset.visible_to(creator))).all()
        assert (
            moderable in session.exec(select(Dataset).where(Dataset.visible_to(permissioned))).all()
        )
        assert moderable in session.exec(select(Dataset).where(Dataset.visible_to(reviewer))).all()
    else:
        assert moderable not in session.exec(select(Dataset).where(Dataset.visible_to())).all()
        assert (
            moderable not in session.exec(select(Dataset).where(Dataset.visible_to(public))).all()
        )
        assert (
            moderable not in session.exec(select(Dataset).where(Dataset.visible_to(creator))).all()
        )
        assert (
            moderable in session.exec(select(Dataset).where(Dataset.visible_to(permissioned))).all()
        )
        assert moderable in session.exec(select(Dataset).where(Dataset.visible_to(reviewer))).all()


def test_editable_base(dataset, session):
    """
    Editable items preserve history when basic attributes are changed
    """
    ds: Dataset = dataset()

    # one change
    ds.title = "NewTitle"
    session.add(ds)
    session.commit()

    # multiple changed
    ds.title = "ThirdTitle"
    ds.description = "A different description"
    session.add(ds)
    session.commit()

    # set to null
    ds.description = None
    session.add(ds)
    session.commit()

    # assign same value
    # FIXME: since we are using an after_flush event, we can't detect changes accurately
    # so this is incorrectly detected as a new version - which is not a huge deal,
    # but it's not perfect.
    ds.title = "ThirdTitle"
    session.add(ds)
    session.commit()

    ds_versions = session.exec(select(Dataset.history_cls())).all()
    # 4 because initial creation should be stored
    assert len(ds_versions) == 5
    assert ds_versions[1].title == "NewTitle"
    assert ds_versions[2].title == "ThirdTitle"
    assert ds_versions[1].description != "A different description"
    assert ds_versions[2].description == "A different description"
    assert ds_versions[3].description is None


def test_editable_one_to_many(dataset, session):
    """
    Editable child objects preserve history when they are changed within their parents

    By "child" objects we mean objects that are never used on their own,
    and we would expect the parent to be the one being committed -
    or at least in the session - when they are updated.
    We probably shouldn't reversion every related object every time anything changes.
    """
    ds: Dataset = dataset()

    # need to create a version of the parent here even if it doesn't change
    # otherwise we wouldn't be able to associate the new part with this version of the dataset
    part = DatasetPart(part_slug="part")
    ds.parts.append(part)
    session.add(ds)
    session.commit()

    # update history in a editable child object but not the parent
    # this one we can't detect with a version, but detect by selecting
    # related items that were edited prior to the following version of the parent
    ds.parts[0].part_slug = "part2"
    session.add(ds)
    session.commit()

    ds_versions = session.exec(select(Dataset.history_cls())).all()
    part_versions = session.exec(select(DatasetPart.history_cls())).all()

    assert len(ds_versions) == 2
    assert len(part_versions) == 2
    assert part_versions[0].part_slug == "part"
    assert part_versions[1].part_slug == "part2"
    assert part_versions[0].version_created_at == ds_versions[1].version_created_at


def test_editable_one_to_many_deletion(dataset, session):
    """Record deletions in one to many as versions that have their fk to the parent nulled out"""
    ds: Dataset = dataset()

    url1 = DatasetURL.get_item("https://example.com/1", session=session)
    url2 = DatasetURL.get_item("https://example.com/2", session=session)
    url3 = DatasetURL.get_item("https://example.com/3", session=session)
    ds.urls = [url1, url2, url3]
    session.add(ds)
    session.commit()

    ds.urls = [url1, url3]
    session.add(ds)
    session.commit()

    urls = session.exec(select(DatasetURL)).all()
    ds_history = session.exec(select(Dataset.history_cls())).all()
    url_history = session.exec(select(DatasetURL.history_cls())).all()
    assert len(ds_history) == 3
    history_groups = defaultdict(list)
    for item in url_history:
        history_groups[item.version_created_at].append(item)

    # didn't make new urls each time
    assert len(urls) == 3

    assert len(history_groups) == 3
    timestamps = list(history_groups.keys())
    # two initial urls
    assert len(history_groups[timestamps[0]]) == 2
    # then three assigned
    assert len(history_groups[timestamps[1]]) == 3
    # two assigned and one removed
    assert len(history_groups[timestamps[2]]) == 3

    # unassigned url2 in the last step
    assert [item for item in history_groups[timestamps[2]] if item.url == url2.url][
        0
    ].dataset_id is None


def test_editable_many_to_many(dataset, session):
    ds: Dataset = dataset()
    tag_states = []
    n_tags = len(ds.tags)
    tag_states.append([t.tag for t in ds.tags])

    ds.title = "NewTitle"
    ds.tags.append(Tag(tag="newtag"))
    session.add(ds)
    session.commit()
    session.refresh(ds)
    n_tags += len(ds.tags)
    tag_states.append([t.tag for t in ds.tags])

    ds.title = "ThirdTitle"
    del ds.tags[0]
    n_tags += 1
    session.add(ds)
    session.commit()
    session.refresh(ds)
    n_tags += len(ds.tags)
    tag_states.append([t.tag for t in ds.tags])

    # change tags without changing parent
    ds.tags.append(Tag(tag="thirdtag"))
    session.add(ds)
    session.commit()
    session.refresh(ds)
    n_tags += len(ds.tags)
    tag_states.append([t.tag for t in ds.tags])

    ds_versions = session.exec(select(Dataset.history_cls())).all()
    tag_link_versions = session.exec(select(DatasetTagLink.history_cls())).all()
    tags = session.exec(select(Tag)).all()
    tags_by_id = {tag.tag_id: tag.tag for tag in tags}

    assert len(ds_versions) == 4
    assert len(tag_link_versions) == n_tags

    uq_timestamps = list(dict.fromkeys([t.version_created_at for t in tag_link_versions]))
    assert len(uq_timestamps) == len(ds_versions)
    assert len(uq_timestamps) == len(tag_states)
    for i, state in enumerate(tag_states):
        version_tags = [
            tags_by_id[t.tag_id]
            for t in tag_link_versions
            if t.version_created_at == uq_timestamps[i] and not t.version_is_deletion
        ]
        assert set(version_tags) == set(state)

    deleted = [t for t in tag_link_versions if t.version_is_deletion]
    assert len(deleted) == 1
    deleted_tag = [t for t in tags if t.tag_id == deleted[0].tag_id][0]
    assert deleted_tag.tag == tag_states[0][0]


def test_editable_disable(dataset, session, set_config):
    """
    We can disable editing
    """
    set_config(enable_versions=False)
    ds: Dataset = dataset()

    # one change
    ds.title = "NewTitle"
    session.add(ds)
    session.commit()

    ds_versions = session.exec(select(Dataset.history_cls())).all()
    assert len(ds_versions) == 0
