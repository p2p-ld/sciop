from faker import Faker


def test_tags_datasets_json(client, dataset):
    """
    Test that we can get datasets from a tag feed.

    Doesn't test correctness of feed, just that it works.
    """
    fake = Faker()
    slugs = []
    for _ in range(5):
        new_slug = "-".join([w.lower() for w in fake.words(nb=3)])
        slugs.append(new_slug)
        dataset(slug=new_slug, tags=["atag"])

    res = client.get("/tags/atag/datasets")
    assert res.status_code == 200
    data = res.json()

    got_slugs = [item["slug"] for item in data["items"]]
    assert set(slugs) == set(got_slugs)
