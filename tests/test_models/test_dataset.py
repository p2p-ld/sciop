from textwrap import dedent

import pytest

from sciop.models import Dataset, DatasetCreate, DatasetPart
from sciop.models.dataset import PREFIX_PATTERN
from sciop.testing.fabricators import default_dataset


def test_dataset_slugification():
    """
    Dataset slugs get slugified
    """
    ds = default_dataset()
    ds["slug"] = "This!!! Is not a SLUG!!!! AT ALL!!!2!"

    dataset = DatasetCreate(**ds)
    assert dataset.slug == "this-is-not-a-slug-at-all-2"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("aaa", ["aaa"]),
        (["aaa"], ["aaa"]),
        (["aaa", ""], ["aaa"]),
        (["single,level,comma,split"], ["single", "level", "comma", "split"]),
        (["double,level", "comma,split"], ["double", "level", "comma", "split"]),
    ],
)
def test_tag_splitting(value, expected):
    kwargs = default_dataset()
    kwargs["tags"] = value
    dataset = DatasetCreate(**kwargs)
    assert dataset.tags == expected


def test_dataset_slug_prefixing(dataset, session):
    """
    Dataset slugs are prefixed to avoid uniqueness collisions on removal
    """
    slug = "the-cool-slug"
    ds: Dataset = dataset(slug=slug)
    assert not ds.is_removed
    ds.is_removed = True
    session.add(ds)
    session.commit()
    session.refresh(ds)
    assert ds.is_removed
    assert PREFIX_PATTERN.fullmatch(ds.slug)
    assert ds.slug != slug
    ds.is_removed = False
    session.add(ds)
    session.commit()
    session.refresh(ds)
    assert not ds.is_removed
    assert ds.slug == slug


def test_dataset_description_html_rendering(dataset, session):
    """
    Dataset descriptions are rendered to html
    """
    description = dedent(
        """\
            * I can haz
            * markdown lists
        """
    )
    ds: Dataset = dataset(description=description)
    assert ds.description == description
    assert (
        ds.description_html
        == '<div class="markdown"><ul>\n<li>I can haz</li>\n<li>markdown lists</li>\n</ul></div>'
    )
    new_description = "A new description"
    ds.description = new_description
    session.add(ds)
    session.commit()
    session.refresh(ds)
    assert ds.description == new_description
    assert ds.description_html == '<div class="markdown"><p>A new description</p></div>'


def test_dataset_part_slug_prefixing(dataset, session):
    """
    Dataset slugs are prefixed to avoid uniqueness collisions on removal
    """
    part_slug = "part-1"
    ds: Dataset = dataset(parts=[DatasetPart(part_slug=part_slug)])
    part = ds.parts[0]
    assert not part.is_removed
    part.is_removed = True
    session.add(part)
    session.commit()
    session.refresh(part)
    assert part.is_removed
    assert PREFIX_PATTERN.fullmatch(part.part_slug)
    assert part.part_slug != part_slug
    part.is_removed = False
    session.add(part)
    session.commit()
    session.refresh(part)
    assert not part.is_removed
    assert part.part_slug == part_slug


def test_dataset_part_description_html_rendering(dataset, session):
    """
    Dataset Part descriptions are rendered to html
    """
    description = dedent(
        """\
            * I can haz
            * markdown lists
        """
    )
    ds: Dataset = dataset(parts=[DatasetPart(part_slug="asdf", description=description)])
    part = ds.parts[0]
    assert part.description == description
    assert (
        part.description_html
        == '<div class="markdown"><ul>\n<li>I can haz</li>\n<li>markdown lists</li>\n</ul></div>'
    )
    new_description = "A new description"
    part.description = new_description
    session.add(part)
    session.commit()
    session.refresh(part)
    assert part.description == new_description
    assert part.description_html == '<div class="markdown"><p>A new description</p></div>'
