from sciop import crud
from sciop.models import SiteStatsRead
from sciop.services.stats import get_site_stats, update_site_stats


def test_instance_stats_disabled(client, monkeypatch):
    """When instance stats are disabled, we get a 404"""
    from sciop.api.routes import instance

    monkeypatch.setattr(instance.config.site_stats, "enabled", False)

    res = client.get("/api/v1/instance/stats")
    assert res.status_code == 404

    res = client.get("/api/v1/instance/stats/latest")
    assert res.status_code == 404


async def test_instance_stats(client, countables, session):
    """
    We can get instance stats, when available.

    Correctness of numbers is tested elsewhere,
    we just test that this method works and the results validate
    """
    n_periods = 5
    for _ in range(n_periods):
        await update_site_stats()
    res = client.get("/api/v1/instance/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == n_periods

    expected = SiteStatsRead.model_validate(get_site_stats(session))
    for item in data["items"]:
        validated = SiteStatsRead(**item)
        assert validated.model_dump(exclude={"created_at"}) == expected.model_dump(
            exclude={"created_at"}
        )


async def test_instance_stats_latest(client, countables, session):
    """
    We can get the latest instance stats
    """
    await update_site_stats()
    res = client.get("/api/v1/instance/stats/latest")
    assert res.status_code == 200
    data = res.json()
    validated = SiteStatsRead(**data)
    expected = SiteStatsRead.model_validate(crud.get_latest_site_stats(session=session))
    assert validated == expected
