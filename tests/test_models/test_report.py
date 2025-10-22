from sciop.models.report import ReportType


def test_report_type_description():
    """
    Report type descriptions should be available as a property
    Returns:

    """
    assert "instance rules" in ReportType.rules.description


def test_report_target(reported_item):
    """the `target` property gets the correct item"""
    item, report = reported_item
    assert report.target is reported_item


def test_report_target_account(reported_item, reported_account):
    """The `target_account` property gets either the reported account or the creator of the item"""
    item, report = reported_item
    assert report.target_account is reported_account
