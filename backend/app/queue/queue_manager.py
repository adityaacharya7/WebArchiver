"""
Persistent database-backed submission queue manager.
Handles atomic worker leasing, crash recovery, priority scheduling, and exponential backoff.
"""
from datetime import timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from backend.app.core.config import settings
from backend.app.db.models import QueueItem, Url, Domain, utc_now

logger = logging.getLogger(__name__)


class QueueManager:
    """Manages persistent database queue items."""

    @staticmethod
    def enqueue_urls(
        db: Session,
        url_ids: list[int],
        services: list[str] | None = None,
        priority: int = 0,
    ) -> int:
        """
        Enqueue URLs for archival processing across specified services.
        Avoids creating duplicate pending/in_progress queue entries.
        """
        if not url_ids:
            return 0

        target_services = services or ["wayback"]
        added_count = 0
        now = utc_now()

        # Batch check existing active queue items in chunks of 500 to avoid N*M query overhead
        existing_set: set[tuple[int, str]] = set()
        for i in range(0, len(url_ids), 500):
            chunk = url_ids[i:i + 500]
            rows = (
                db.query(QueueItem.url_id, QueueItem.service)
                .filter(
                    QueueItem.url_id.in_(chunk),
                    QueueItem.service.in_(target_services),
                    QueueItem.status.in_(["pending", "in_progress"]),
                )
                .all()
            )
            for r in rows:
                existing_set.add((r[0], r[1]))

        for url_id in url_ids:
            for service in target_services:
                if (url_id, service) not in existing_set:
                    item = QueueItem(
                        url_id=url_id,
                        service=service,
                        status="pending",
                        priority=priority,
                        attempts=0,
                        leased_at=None,
                        created_at=now,
                    )
                    db.add(item)
                    existing_set.add((url_id, service))
                    added_count += 1

        db.commit()
        return added_count

    @staticmethod
    def reclaim_expired_leases(db: Session, lease_timeout_seconds: int | None = None) -> int:
        """
        Crash safety mechanism:
        Reclaims queue items that were claimed by a worker but never finished
        within lease_timeout_seconds (e.g. server crash, worker killed).
        Resets them to 'pending'.
        """
        timeout = lease_timeout_seconds or settings.WORKER_LEASE_TIMEOUT_SECONDS
        cutoff = utc_now() - timedelta(seconds=timeout)

        expired_items = (
            db.query(QueueItem)
            .filter(
                QueueItem.status == "in_progress",
                QueueItem.leased_at < cutoff,
            )
            .all()
        )

        count = len(expired_items)
        if count > 0:
            for item in expired_items:
                logger.info(f"Reclaiming expired lease on queue item {item.id} (url_id={item.url_id})")
                item.status = "pending"
                item.leased_at = None
                item.next_retry_at = utc_now()
            db.commit()

        return count

    @staticmethod
    def claim_next_batch(
        db: Session,
        service: str | None = None,
        batch_size: int = 5,
        max_retries: int | None = None,
    ) -> list[QueueItem]:
        """
        Atomically claim next batch of pending items eligible for processing.
        Respects retry backoff and priority ordering.
        """
        # First ensure any dead worker leases are reclaimed
        QueueManager.reclaim_expired_leases(db)

        retries_limit = max_retries or settings.MAX_SUBMISSION_RETRIES
        now = utc_now()

        query = (
            db.query(QueueItem)
            .filter(
                QueueItem.status == "pending",
                QueueItem.attempts < retries_limit,
                or_(QueueItem.next_retry_at.is_(None), QueueItem.next_retry_at <= now),
            )
        )

        if service:
            query = query.filter(QueueItem.service == service)

        # Order by priority (highest first), then FIFO
        items = query.order_by(QueueItem.priority.desc(), QueueItem.id.asc()).limit(batch_size).all()

        for item in items:
            item.status = "in_progress"
            item.leased_at = now
            item.attempts += 1

        db.commit()
        return items

    @staticmethod
    def mark_completed(db: Session, queue_item_id: int):
        """Mark a queue item as successfully processed."""
        item = db.query(QueueItem).filter(QueueItem.id == queue_item_id).first()
        if item:
            item.status = "done"
            item.leased_at = None
            db.commit()

    @staticmethod
    def mark_failed(
        db: Session,
        queue_item_id: int,
        error_message: str,
        max_retries: int | None = None,
        backoff_base: int | None = None,
    ):
        """
        Mark a queue item as failed with exponential backoff retry scheduling,
        or mark permanent failure for manual review if attempts exceeded.
        """
        item = db.query(QueueItem).filter(QueueItem.id == queue_item_id).first()
        if not item:
            return

        retries_limit = max_retries or settings.MAX_SUBMISSION_RETRIES
        base_seconds = backoff_base or settings.RETRY_BACKOFF_BASE_SECONDS
        now = utc_now()

        item.last_error = error_message
        item.leased_at = None

        if item.attempts >= retries_limit:
            item.status = "failed_permanent"
            item.next_retry_at = None
            logger.warning(
                f"QueueItem {item.id} exceeded max retries ({item.attempts}/{retries_limit}). "
                f"Marked failed_permanent: {error_message}"
            )
        else:
            item.status = "pending"
            # Exponential backoff: base * 2^(attempts - 1) with safe ceiling of 3600s
            safe_exponent = min(max(item.attempts - 1, 0), 10)
            backoff_delay = min(base_seconds * (2 ** safe_exponent), 3600)
            item.next_retry_at = now + timedelta(seconds=backoff_delay)
            logger.info(
                f"QueueItem {item.id} failed attempt {item.attempts}/{retries_limit}. "
                f"Retrying in {backoff_delay}s: {error_message}"
            )

        db.commit()

    @staticmethod
    def retry_permanent_failures(db: Session, domain_id: int | None = None, user_id: int | None = None) -> int:
        """Reset failed_permanent items back to pending for manual retry, scoped to domain or user."""
        query = db.query(QueueItem).filter(QueueItem.status == "failed_permanent")
        if domain_id:
            query = query.join(Url).filter(Url.domain_id == domain_id)
        elif user_id:
            query = query.join(Url).join(Domain).filter(Domain.user_id == user_id)

        items = query.all()
        count = len(items)
        now = utc_now()
        for item in items:
            item.status = "pending"
            item.attempts = 0
            item.last_error = None
            item.next_retry_at = now
            item.leased_at = None

        db.commit()
        return count

    @staticmethod
    def get_stats(db: Session, domain_id: int | None = None, user_id: int | None = None) -> dict:
        """Get summary stats of the queue, scoped to domain or user."""
        query = db.query(QueueItem)
        if domain_id:
            query = query.join(Url).filter(Url.domain_id == domain_id)
        elif user_id:
            query = query.join(Url).join(Domain).filter(Domain.user_id == user_id)

        total = query.count()
        pending = query.filter(QueueItem.status == "pending").count()
        in_progress = query.filter(QueueItem.status == "in_progress").count()
        done = query.filter(QueueItem.status == "done").count()
        failed_permanent = query.filter(QueueItem.status == "failed_permanent").count()

        return {
            "total": total,
            "pending": pending,
            "in_progress": in_progress,
            "done": done,
            "failed_permanent": failed_permanent,
        }
