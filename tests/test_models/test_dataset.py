from sciop.models import DatasetCreate


def test_dataset_slugification(default_dataset):
    """
    Dataset slugs get slugified
    """
    default_dataset["slug"] = "This!!! Is not a SLUG!!!! AT ALL!!!2!"

    dataset = DatasetCreate(**default_dataset)
    assert dataset.slug == "this-is-not-a-slug-at-all-2"
