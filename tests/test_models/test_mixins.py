import pdb
from enum import StrEnum
from typing import Optional

import pytest
from sqlmodel import Field, Session, select

from sciop.models import Dataset, Tag
from sciop.models.mixins.enum import EnumTableMixin


def test_full_text_search(session):
    """
    Weak test for whether full text search merely works.
    """

    match_ok = Dataset(
        title="Matches a single thing once like key",
        slug="matching-ok",
        publisher="Agency of matching ok",
    )
    match_good = Dataset(
        title="Matches several keywords like key and word several times, see key key key",
        slug="matching-good",
        publisher="Agency of matching good",
    )
    no_match = Dataset(
        title="Nothing in here",
        slug="not-good",
        publisher="Agency of not good",
    )

    session.add(match_ok)
    session.add(match_good)
    session.add(no_match)
    session.commit()

    results = Dataset.search("key", session)

    assert len(results) == 2
    assert results[0].Dataset.slug == match_good.slug
    assert results[1].Dataset.slug == match_ok.slug


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
    Moderable items should be visible to creators and moderators if not removed,
    even if not yet approved
    """
    creator = account(username="creator")
    public = account(username="public")
    reviewer = account(username="reviewer", scopes=["review"])
    moderable = dataset()
    moderable.account = creator
    moderable.is_approved = is_approved
    moderable.is_removed = is_removed
    session.add(moderable)
    session.commit()
    session.refresh(moderable)

    if is_removed:
        assert not moderable.visible_to()
        assert not moderable.visible_to(public)
        assert not moderable.visible_to(creator)
        assert not moderable.visible_to(reviewer)
    elif is_approved:
        assert moderable.visible_to()
        assert moderable.visible_to(public)
        assert moderable.visible_to(creator)
        assert moderable.visible_to(reviewer)
    else:
        assert not moderable.visible_to()
        assert not moderable.visible_to(public)
        assert moderable.visible_to(creator)
        assert moderable.visible_to(reviewer)


@pytest.mark.parametrize("is_approved", [True, False])
@pytest.mark.parametrize("is_removed", [True, False])
def test_visible_to_expression(dataset, account, is_approved, is_removed, session):
    """
    Moderable items should be visible to creators and moderators if not removed,
    even if not yet approved when used as an expression
    """
    creator = account(username="creator")
    public = account(username="public")
    reviewer = account(username="reviewer", scopes=["review"])
    moderable = dataset()
    moderable.account = creator
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
    elif is_approved:
        assert moderable in session.exec(select(Dataset).where(Dataset.visible_to())).all()
        assert moderable in session.exec(select(Dataset).where(Dataset.visible_to(public))).all()
        assert moderable in session.exec(select(Dataset).where(Dataset.visible_to(creator))).all()
        assert moderable in session.exec(select(Dataset).where(Dataset.visible_to(reviewer))).all()
    else:
        assert moderable not in session.exec(select(Dataset).where(Dataset.visible_to())).all()
        assert (
            moderable not in session.exec(select(Dataset).where(Dataset.visible_to(public))).all()
        )
        assert moderable in session.exec(select(Dataset).where(Dataset.visible_to(creator))).all()
        assert moderable in session.exec(select(Dataset).where(Dataset.visible_to(reviewer))).all()


def test_editable(dataset, session):
    ds = dataset()
    ds.title = "NewTitle"
    ds.tags.append(Tag(tag="newtag"))
    session.add(ds)
    session.commit()

    ds.title = "ThirdTitle"
    del ds.tags[0]
    session.add(ds)
    session.commit()

    ds.title = "FourthTitle"
    ds.tags.append(Tag(tag="thirdtag"))
    session.add(ds)
    session.commit()

    # FIXME: need to correct the change detection logic to catch cases where the parent table is not modified
