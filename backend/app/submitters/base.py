"""
Base submitter interface and result data structures.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class SubmissionResult:
    """Represents the outcome of an archival submission attempt."""
    success: bool
    service: str
    archive_url: str | None = None
    archive_id: str | None = None
    http_status: int | None = None
    error_message: str | None = None
    submitted_at: datetime = None
    completed_at: datetime = None

    def __post_init__(self):
        if self.submitted_at is None:
            self.submitted_at = utc_now()
        if self.completed_at is None:
            self.completed_at = utc_now()


class BaseSubmitter(ABC):
    """Abstract interface for web archive submission services."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def submit(self, url: str) -> SubmissionResult:
        """Submit URL to the archive service and return outcome."""
        pass
