from bs4 import BeautifulSoup
import pytest


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
