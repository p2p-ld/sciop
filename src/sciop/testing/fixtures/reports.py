from typing import Callable as C
from typing import TypeAlias

import pytest
from sqlmodel import Session

from sciop.models import Account, Dataset, DatasetPart, Report, Upload

ReportableClass: TypeAlias = Account | Dataset | DatasetPart | Upload


@pytest.fixture()
def reporting_account(account: C[..., Account]) -> Account:
    acct = account(username="reporter")
    return acct


@pytest.fixture()
def reported_account(account: C[..., Account]) -> Account:
    acct = account(username="reported")
    return acct


@pytest.fixture(params=["account", "dataset", "dataset_part", "upload"])
def reportable_item(
    request: pytest.FixtureRequest,
    dataset: C[..., Dataset],
    dataset_part: C[..., DatasetPart],
    upload: C[..., Upload],
    reported_account: Account,
) -> ReportableClass:
    """
    An item that is to be reported
    """
    acct = reported_account
    if request.param == "account":
        return acct
    elif request.param == "dataset":
        return dataset(slug="reported", account_=acct)
    elif request.param == "dataset_part":
        return dataset_part(part_slug="reported", account_=acct)
    elif request.param == "upload":
        return upload(account_=acct)


@pytest.fixture
def reported_item(
    reportable_item: ReportableClass, session: Session, reporting_account: Account
) -> tuple[ReportableClass, Report]:
    """
    An item that is reported and its associated report
    """
    acct = reporting_account
    kwargs = {"report_type": "rules"}
    if isinstance(reportable_item, Account):
        kwargs["target_account"] = reportable_item
    elif isinstance(reportable_item, Dataset):
        kwargs["target_dataset"] = reportable_item
    elif isinstance(reportable_item, DatasetPart):
        kwargs["target_dataset_part"] = reportable_item
    elif isinstance(reportable_item, Upload):
        kwargs["target_upload"] = reportable_item
    else:
        raise ValueError(f"Unknown item type: {reportable_item}")
    report = Report(opened_by=acct, **kwargs)
    session.add(report)
    session.commit()
    session.refresh(report)
    return reportable_item, report


@pytest.fixture(params=["admin", "reviewer", "reporter", "rando"])
def resolving_account(
    request: pytest.FixtureRequest, account: C[..., Account], reporting_account: Account
) -> Account:
    """
    Account attempting to resolve report, with varying permissions levels
    """
    if request.param == "admin":
        acct = account(username=request.param, scopes=["admin"])
    elif request.param == "reviewer":
        acct = account(username=request.param, scopes=["review"])
    elif request.param == "reporter":
        return reporting_account
    elif request.param == "rando":
        acct = account(username=request.param)
    else:
        raise ValueError()
    return acct
