"""
Incremental Archiving and Change Detection Service.
Identifies new URLs, unchanged URLs, and content changes across re-scans.
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.db.models import Url, Submission, QueueItem, Domain
from backend.app.queue.queue_manager import QueueManager

logger = logging.getLogger(__name__)


class ChangeDetector:
    """
    Analyzes domain inventory for incremental updates, modified pages,
    and unarchived URLs to prevent redundant archive submissions.
    """

    @staticmethod
    def inspect_domain_inventory(db: Session, domain_id: int) -> dict:
        """
        Categorize all URLs of a domain:
        - never_archived: URLs with 0 successful submissions
        - successfully_archived: URLs with >= 1 successful submission
        - pending_in_queue: URLs currently waiting in the submission queue
        - total_inventory: Total unique discovered URLs
        """
        domain = db.query(Domain).filter(Domain.id == domain_id).first()
        if not domain:
            return {}

        total_urls = db.query(Url).filter(Url.domain_id == domain_id).count()

        # URLs with successful submissions
        archived_url_ids = (
            db.query(Submission.url_id)
            .join(Url)
            .filter(Url.domain_id == domain_id, Submission.status == "success")
            .distinct()
            .all()
        )
        archived_ids_set = {row[0] for row in archived_url_ids}

        # URLs currently in queue
        queued_url_ids = (
            db.query(QueueItem.url_id)
            .join(Url)
            .filter(
                Url.domain_id == domain_id,
                QueueItem.status.in_(["pending", "in_progress"]),
            )
            .distinct()
            .all()
        )
        queued_ids_set = {row[0] for row in queued_url_ids}

        # Unarchived URL IDs (never succeeded and not currently active in queue)
        all_urls = db.query(Url).filter(Url.domain_id == domain_id).all()
        never_archived_ids = [
            u.id for u in all_urls
            if u.id not in archived_ids_set and u.id not in queued_ids_set
        ]

        # Modified URLs whose content changed across crawls and need updated snapshot
        changed_ids = [
            u.id for u in all_urls
            if getattr(u, "content_changed", False) and u.id not in queued_ids_set
        ]

        return {
            "domain_id": domain_id,
            "domain": domain.domain,
            "total_urls": total_urls,
            "archived_urls_count": len(archived_ids_set),
            "queued_urls_count": len(queued_ids_set),
            "unarchived_urls_count": len(never_archived_ids),
            "changed_urls_count": len(changed_ids),
            "unarchived_url_ids": never_archived_ids,
            "changed_url_ids": changed_ids,
        }

    @staticmethod
    def enqueue_incremental(
        db: Session,
        domain_id: int,
        services: list[str] | None = None,
        force_all: bool = False,
        rearchive_changed: bool = False,
        priority: int = 0,
    ) -> dict:
        """
        Enqueue URLs for archival:
        - If force_all=True: Enqueues all URLs in the domain for a fresh snapshot.
        - If rearchive_changed=True: Enqueues unarchived URLs + any URLs with detected content modifications.
        - If force_all=False (default): Enqueues only URLs never archived or not currently queued.
        """
        target_services = services or ["wayback"]

        if force_all:
            urls = db.query(Url).filter(Url.domain_id == domain_id).all()
            target_ids = [u.id for u in urls]
            mode_name = "force_all"
        elif rearchive_changed:
            inventory = ChangeDetector.inspect_domain_inventory(db, domain_id)
            combined = inventory.get("unarchived_url_ids", []) + inventory.get("changed_url_ids", [])
            target_ids = list(dict.fromkeys(combined))
            mode_name = "rearchive_changed_and_unarchived"
        else:
            inventory = ChangeDetector.inspect_domain_inventory(db, domain_id)
            target_ids = inventory.get("unarchived_url_ids", [])
            mode_name = "incremental_unarchived_only"

        enqueued_count = QueueManager.enqueue_urls(
            db=db,
            url_ids=target_ids,
            services=target_services,
            priority=priority,
        )

        return {
            "domain_id": domain_id,
            "eligible_urls": len(target_ids),
            "items_enqueued": enqueued_count,
            "services": target_services,
            "mode": mode_name,
        }
