"""Submitters package."""
from backend.app.submitters.base import BaseSubmitter, SubmissionResult
from backend.app.submitters.wayback import WaybackSubmitter
from backend.app.submitters.archive_today import ArchiveTodaySubmitter
from backend.app.submitters.ghostarchive import GhostarchiveSubmitter
from backend.app.submitters.registry import (
    get_submitter,
    list_available_services,
    register_submitter,
)

__all__ = [
    "BaseSubmitter",
    "SubmissionResult",
    "WaybackSubmitter",
    "ArchiveTodaySubmitter",
    "GhostarchiveSubmitter",
    "get_submitter",
    "list_available_services",
    "register_submitter",
]
