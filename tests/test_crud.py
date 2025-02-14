from sqlmodel import select

from sciop import crud
from sciop.models import DatasetCreate, Tag


def test_create_dataset_tags(session, default_dataset):
    """
    Creating a new dataset correctly uses existing tags and makes new ones
    """
    # FIXME: implement transactional tests...
    existing_tag = session.exec(select(Tag).filter(Tag.tag == "existing")).first()
    if not existing_tag:
        existing_tag = Tag(tag="existing")
        session.add(existing_tag)
        session.commit()
        session.refresh(existing_tag)

    a = default_dataset.copy()
    a["tags"].append("existing")
    a["tags"].append("a-new-one")
    a["title"] = "Dataset A"
    a["slug"] = "dataset-a"

    b = default_dataset.copy()
    b["tags"].append("existing")
    b["tags"].append("another-new-one")
    b["title"] = "Dataset B"
    b["slug"] = "dataset-B"

    if dataset_a := crud.get_dataset(session=session, dataset_slug="dataset-a"):
        session.delete(dataset_a)
    if dataset_b := crud.get_dataset(session=session, dataset_slug="dataset-b"):
        session.delete(dataset_b)
    session.commit()

    dataset_a = crud.create_dataset(session=session, dataset_create=DatasetCreate(**a))
    dataset_b = crud.create_dataset(session=session, dataset_create=DatasetCreate(**b))

    existing_a = [tag for tag in dataset_a.tags if tag.tag == "existing"][0]
    existing_b = [tag for tag in dataset_b.tags if tag.tag == "existing"][0]

    assert existing_a.tag_id == existing_b.tag_id == existing_tag.tag_id

    assert len([tag for tag in dataset_a.tags if tag.tag == "a-new-one"]) == 1
    assert len([tag for tag in dataset_b.tags if tag.tag == "another-new-one"]) == 1
