"""
Registry for archive submitters.
"""
from backend.app.submitters.base import BaseSubmitter
from backend.app.submitters.wayback import WaybackSubmitter
from backend.app.submitters.archive_today import ArchiveTodaySubmitter
from backend.app.submitters.ghostarchive import GhostarchiveSubmitter

_SUBMITTERS: dict[str, BaseSubmitter] = {
    "wayback": WaybackSubmitter(),
    "archive_today": ArchiveTodaySubmitter(),
    "ghostarchive": GhostarchiveSubmitter(),
}


def get_submitter(service_name: str) -> BaseSubmitter | None:
    """Retrieve submitter instance by service name."""
    return _SUBMITTERS.get(service_name.lower().strip())


def list_available_services() -> list[str]:
    """List all registered archive service names."""
    return list(_SUBMITTERS.keys())


def register_submitter(service_name: str, submitter: BaseSubmitter):
    """Dynamically register a new submitter."""
    _SUBMITTERS[service_name.lower().strip()] = submitter
