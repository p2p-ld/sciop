"""
This needs to be out of the module to run at install time...
"""

import subprocess
from datetime import datetime, timedelta


def get_version() -> str:
    """
    Get a calver version like
    "YYYYMM.DD.N+{HASH}"
    where `N` is the commit number for that day and `HASH` is the short hash
    """
    try:
        timestamp = _last_commit_timestamp()

        # get n commits in that day, 0-indexed
        yesterday = timestamp - timedelta(days=1)
        n_commits = max(_n_commits_between_timestamps(yesterday, timestamp) - 1, 0)
        short_hash = _short_hash()

        return f"{timestamp.year}{timestamp.month:02}.{timestamp.day:02}.{n_commits}+{short_hash}"
    except:  # noqa: E722
        # version isn't really all that important for this project yet...
        # so if there are any git errors, just ignore them
        return "000000.00.00+0000000"


def _last_commit_timestamp(branch: str = "main") -> datetime:
    out = subprocess.run(["git", "log", branch, "-1", "--format=%at"], capture_output=True)
    unix_timestamp = out.stdout.decode("utf-8").strip()
    timestamp = datetime.fromtimestamp(float(unix_timestamp))
    return timestamp


def _n_commits_between_timestamps(start: datetime, end: datetime, branch: str = "main") -> int:
    """start is exclusive, end is inclusive - only sensitive to dates not times"""
    out = subprocess.run(
        [
            "git",
            "log",
            branch,
            "--oneline",
            f'--since="{start.year}-{start.month}-{start.day}"',
            f'--until="{end.year}-{end.month}-{end.day}"',
        ],
        capture_output=True,
    )
    n_commits = len(out.stdout.decode("utf-8").strip().split("\n"))
    return n_commits


def _short_hash() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
    )
    return out.stdout.decode("utf-8").strip()
