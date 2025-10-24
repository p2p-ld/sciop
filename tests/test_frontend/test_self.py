import re

import pytest
from bs4 import BeautifulSoup
from playwright.async_api import Page, expect

from sciop.models import Account, AuditLog, DatasetPart, Webseed
from sciop.types import ModerationAction, Scopes


@pytest.mark.playwright
@pytest.mark.asyncio(loop_scope="session")
async def test_account_admin(page_as_admin: Page, account, session):
    page = page_as_admin
    rando: Account = account(username="rando")
    assert not rando.has_scope("upload")

    await page.goto("http://127.0.0.1:8080/self/admin")
    await expect(page.locator("#rando-scope-upload")).to_have_class("toggle-button")
    await page.locator("#rando-scope-upload").click()
    await expect(page.locator("#rando-scope-upload")).to_have_class("toggle-button checked")

    session.refresh(rando)
    assert rando.has_scope("upload")

    await page.locator("#rando-scope-upload").click()
    await expect(page.locator("#rando-scope-upload")).to_have_class("toggle-button")


def test_audit_log_entries(
    client, admin_user, admin_auth_header, account, dataset, upload, session
):
    """
    Audit log entries are correctly displayed
    """
    # create entities to do audit log things to
    rando = account(username="rando")
    ds = dataset(account_=rando, is_approved=False)
    part = DatasetPart(dataset=ds, account=rando, part_slug="examplea_part")
    session.add(part)
    ul = upload(dataset_=ds, account_=rando, is_approved=False)
    ws = Webseed(
        is_approved=False, account=rando, url="https://example.com/", status="pending_review"
    )
    ul.torrent.webseeds = [ws]
    session.add(ul.torrent)
    session.commit()

    # make the audit log things
    entries = [
        AuditLog(actor=admin_user, action=ModerationAction.approve, target_dataset=ds),
        AuditLog(actor=admin_user, action=ModerationAction.approve, target_dataset_part=part),
        AuditLog(actor=admin_user, action=ModerationAction.approve, target_upload=ul),
        AuditLog(actor=admin_user, action=ModerationAction.approve, target_webseed=ws),
        AuditLog(
            actor=admin_user,
            action=ModerationAction.add_scope,
            target_account=rando,
            value=Scopes.submit,
        ),
    ]
    for e in entries:
        session.add(e)
    session.commit()
    expected = [
        {"actor": "admin", "action": "approve", "target": ds.slug},
        {"actor": "admin", "action": "approve", "target": f"{ds.slug}/{part.part_slug}"},
        {"actor": "admin", "action": "approve", "target": ul.short_hash},
        {"actor": "admin", "action": "approve", "target": ws.url},
        {"actor": "admin", "action": "add_scope", "value": "submit", "target": rando.username},
    ]

    res = client.get("/self/log/page", headers={"HX-Request": "true", **admin_auth_header})
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "lxml")
    log_rows = soup.select("table.audit-log-table tr.table-row")
    assert len(log_rows) == len(expected)
    for row, e in zip(reversed(log_rows), expected):
        # unpack row
        cells = row.select("td")
        row_vals = {
            "actor": cells[0].text.strip(),
            "action": cells[1].text.strip(),
            "value": cells[2].text.strip(),
            "target": re.sub(r"\s", "", cells[3].text.strip()),
        }
        for e_key in e:
            assert row_vals[e_key] == e[e_key]


@pytest.mark.skip()
def test_show_unapproved_self_datasets():
    pass


@pytest.mark.skip()
def test_show_unapproved_self_dataset_parts():
    pass


@pytest.mark.skip()
def test_show_unapproved_self_uploads():
    pass
