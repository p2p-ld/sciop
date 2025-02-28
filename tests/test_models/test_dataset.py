import pytest

from sciop.models import Dataset, DatasetCreate, DatasetPart
from sciop.models.dataset import PREFIX_PATTERN


def test_dataset_slugification(default_dataset):
    """
    Dataset slugs get slugified
    """
    default_dataset["slug"] = "This!!! Is not a SLUG!!!! AT ALL!!!2!"

    dataset = DatasetCreate(**default_dataset)
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
def test_tag_splitting(default_dataset, value, expected):
    default_dataset["tags"] = value
    dataset = DatasetCreate(**default_dataset)
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
