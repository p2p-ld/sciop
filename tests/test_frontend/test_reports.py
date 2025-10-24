import asyncio

import pytest
from bs4 import BeautifulSoup
from playwright.async_api import Page, expect

from sciop.models import Account, Report
from sciop.testing.fixtures.reports import ReportableClass
from sciop.types import ReportAction


@pytest.mark.parametrize("reportable_item", ["dataset"], indirect=True)
def test_report_message(reporting_account, get_auth_header, client, set_config, reportable_item):
    """
    The instance configured report message is displayed on the report modal
    """
    report_message = (
        "Hey everyone reporting dangerous or invalid items is "
        "basically eating the bugs out of the fur of the instance"
    )
    set_config({"instance.report_message": report_message})

    header = get_auth_header(reporting_account.username)
    res = client.get(
        f"/partials/report?target_type=dataset&target={reportable_item.slug}", headers=header
    )
    assert res.status_code == 200
    soup = BeautifulSoup(res.text, "lxml")
    msg = soup.select_one("p.report-message")
    assert msg.text == report_message


@pytest.mark.playwright
@pytest.mark.asyncio(loop_scope="session")
async def test_create_report(page_as_user: Page, reportable_item: ReportableClass):
    """
    We can create a report and then view it on our /self page
    """
    page = page_as_user
    item = reportable_item
    comment = "hey this is my comment"
    report_type = "fake"

    # open report modal
    await page.goto(f"http://127.0.0.1:8080{reportable_item.frontend_url}")
    await page.get_by_role("button", name="Report").click()
    # allow server to return
    await asyncio.sleep(0.05)

    # fill report
    await page.get_by_text("Show/Hide Option Description").click()
    await page.get_by_label("Report type").select_option(report_type)
    await page.get_by_role("textbox", name="Comment").click()
    await page.get_by_role("textbox", name="Comment").fill(comment)
    await page.get_by_role("button", name="Submit").scroll_into_view_if_needed()
    await page.get_by_role("button", name="Submit").click()
    # allow server to return
    await asyncio.sleep(0.05)

    # close modal
    await page.get_by_role("button", name="close").click()
    # allow server to return
    await asyncio.sleep(0.05)
    await page.locator("#report-modal-container").is_hidden()

    # view report
    await page.locator(".nav-button.account-button").click()
    await asyncio.sleep(0.05)
    await expect(page.locator(".self-greeting")).to_be_visible()
    # avoid clicking the reported item link by setting click position explicitly
    await page.locator("#report-collapsible-1").click(position={"x": 10, "y": 10})

    # report is present
    await expect(page.get_by_role("heading", name="Report #")).to_be_visible()
    await expect(page.get_by_role("cell", name="@user")).to_be_visible()
    await expect(page.get_by_role("cell", name=report_type)).to_be_visible()
    await expect(page.get_by_text(comment)).to_be_visible()

    # item is present
    await page.locator("#report-1 .collapsible-summary").click(position={"x": 10, "y": 10})
    await asyncio.sleep(0.05)


@pytest.mark.playwright
@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("action", ReportAction.__members__.values())
async def test_resolve_report(
    page_as_admin: Page, reported_item: tuple[ReportableClass, Report], action: ReportAction
):
    """
    As an admin, we can resolve a report with each (valid) action.

    Correctness of action behavior is not tested here, see test_api/reports
    for that :) - we're just testing that we can actually take all the actions we should be able to
    from the web ui.
    """
    page = page_as_admin
    item, report = reported_item
    comment = "hey this is my comment too"

    if report.target_type == "account" and action in ("hide", "remove"):
        pytest.skip(f"{action} is invalid for accounts")

    await page.goto("http://127.0.0.1:8080/self/reports/")
    # allow server to return
    await asyncio.sleep(0.05)

    # open in-page version, just checking for visibility for now
    await page.get_by_label("Expand/Collapse").click()
    await asyncio.sleep(0.05)
    await expect(page.locator("#report-1-actions")).to_be_visible()

    # go to report page
    await page.get_by_role("link", name="1").click()
    await asyncio.sleep(0.05)

    # Buttons are present
    await expect(page.locator("#report-1-actions")).to_be_visible()
    for action_key in ReportAction.__members__:
        item_button = page.locator(f'#report-1-actions button[data-action="{action_key}"]')
        if isinstance(item, Account) and action_key in ("hide", "remove"):
            await expect(item_button).not_to_be_visible()
        else:
            await expect(item_button).to_be_visible()

    # take some action
    await page.locator('textarea[name="action_comment"]').fill(comment)
    page.on("dialog", lambda dialog: dialog.accept())
    await page.locator(f'#report-1-actions button[data-action="{action}"]').click()
    await asyncio.sleep(0.05)

    await expect(page.get_by_role("cell", name="Resolved By")).to_be_visible()
    await expect(page.get_by_role("cell", name="Resolved At")).to_be_visible()
    await expect(page.get_by_role("cell", name=action)).to_be_visible()
