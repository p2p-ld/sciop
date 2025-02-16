import pytest

from sciop.models import DatasetCreate


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
