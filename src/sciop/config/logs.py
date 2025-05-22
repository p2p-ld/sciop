from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

LOG_LEVELS = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class LogConfig(BaseModel):
    """
    Configuration for logging
    """

    level: LOG_LEVELS = Field(
        default="INFO",
        description="""
    Severity of log messages to process.
    """,
    )
    level_file: Optional[LOG_LEVELS] = Field(
        default=None,
        description="""
    Severity for file-based logging. If unset, use ``level``
    """,
    )
    level_stdout: Optional[LOG_LEVELS] = Field(
        default=None,
        description="""
    Severity for stream-based logging. If unset, use ``level``
    """,
    )
    file_n: int = Field(
        default=5,
        description="""
    Number of log files to rotate through
    """,
    )
    file_size: int = Field(
        default=2**22,
        description="""
    Maximum size of log files (bytes)
    """,
    )
    request_timing: bool = False
    """Enable timing requests, and logging request time"""

    @field_validator("level", "level_file", "level_stdout", mode="before")
    @classmethod
    def uppercase_levels(cls, value: Optional[str] = None) -> Optional[str]:
        """
        Ensure log level strings are uppercased
        """
        if value is not None:
            value = value.upper()
        return value
