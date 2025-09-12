from sciop.models.report import ReportType


def test_report_type_description():
    """
    Report type descriptions should be available as a property
    Returns:

    """
    assert "instance rules" in ReportType.rules.description
