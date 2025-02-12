from sqlmodel import Session, SQLModel, create_engine

from sciop.models import Dataset

from .conftest import TMP_DIR


def test_full_text_search():
    """
    Weak test for whether full text search merely works.

    # TODO: actual unit tests plz
    """
    # this should really be in a fixture but it's ok since we don't have any other tests yet!
    sqlite_path = TMP_DIR / "db.test.sqlite"
    sqlite_path.unlink(missing_ok=True)
    sqlite_path = f"sqlite:///{str(sqlite_path)}"
    engine = create_engine(sqlite_path)
    Dataset.register_events()

    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
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
