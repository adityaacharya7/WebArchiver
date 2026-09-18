"""
Asynchronous Worker Pool for archive submissions.
Handles controlled concurrency, rate limiting, crash recovery, and status tracking.
"""
import asyncio
import logging
from threading import Thread, Event
from datetime import datetime

from backend.app.core.config import settings
from backend.app.db.database import get_db_context
from backend.app.db.models import QueueItem, Url, Domain, Submission, utc_now
from backend.app.queue.queue_manager import QueueManager
from backend.app.queue.rate_limiter import TokenBucketRateLimiter
from backend.app.submitters.registry import get_submitter

logger = logging.getLogger(__name__)


class WorkerPool:
    """
    Background worker pool managing submission queue processing.
    Runs persistently, honors rate limits, and automatically recovers crashed tasks.
    """

    def __init__(self):
        self._running = False
        self._paused = False
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._processed_count = 0
        self._success_count = 0
        self._failed_count = 0

        # Per-service token bucket rate limiters
        self.limiters = {
            "wayback": TokenBucketRateLimiter(settings.WAYBACK_RATE_LIMIT_PER_MINUTE),
            "archive_today": TokenBucketRateLimiter(settings.ARCHIVE_TODAY_RATE_LIMIT_PER_MINUTE),
            "ghostarchive": TokenBucketRateLimiter(settings.GHOSTARCHIVE_RATE_LIMIT_PER_MINUTE),
        }

    def start(self):
        """Start worker thread."""
        if self._running or (self._thread and self._thread.is_alive()):
            return
        self._running = True
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, name="ArchiverWorkerThread", daemon=True)
        self._thread.start()
        logger.info("WorkerPool started.")

    def stop(self):
        """Signal worker thread to stop."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("WorkerPool stopped.")

    def pause(self):
        """Pause queue processing."""
        self._paused = True
        logger.info("WorkerPool paused.")

    def resume(self):
        """Resume queue processing."""
        self._paused = False
        logger.info("WorkerPool resumed.")

    def is_paused(self) -> bool:
        return self._paused

    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "paused": self._paused,
            "processed_total": self._processed_count,
            "success_total": self._success_count,
            "failed_total": self._failed_count,
        }

    def _run_loop(self):
        """Main thread loop running an asyncio event loop for async submitters."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._worker_cycle())
        finally:
            loop.close()

    async def _worker_cycle(self):
        """Continuous polling cycle."""
        logger.info("Worker execution cycle active.")
        while not self._stop_event.is_set():
            if self._paused:
                await asyncio.sleep(settings.WORKER_POLL_INTERVAL)
                continue

            try:
                processed_any = await self._process_batch()
                if not processed_any:
                    await asyncio.sleep(settings.WORKER_POLL_INTERVAL)
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(settings.WORKER_POLL_INTERVAL)

    async def _process_batch(self) -> bool:
        """Fetch and process one batch of items concurrently."""
        claimed_ids: list[int] = []

        with get_db_context() as db:
            batch_sz = getattr(settings, "MAX_WORKERS", getattr(settings, "WORKER_POOL_SIZE", 5))
            # Atomic claim with automatic recovery of expired leases
            claimed_items = QueueManager.claim_next_batch(
                db,
                batch_size=batch_sz,
            )
            claimed_ids = [item.id for item in claimed_items]

        if not claimed_ids:
            return False

        logger.info(f"Worker claimed batch of {len(claimed_ids)} items for archival submission.")

        # Process batch concurrently using asyncio.gather
        tasks = [self._submit_item(qid) for qid in claimed_ids]
        await asyncio.gather(*tasks, return_exceptions=True)
        return True

    async def _submit_item(self, queue_item_id: int):
        """Process a single queue item with rate limiting and retry handling."""
        with get_db_context() as db:
            item = db.query(QueueItem).filter(QueueItem.id == queue_item_id).first()
            if not item:
                return

            url_rec = db.query(Url).filter(Url.id == item.url_id).first()
            if not url_rec:
                QueueManager.mark_failed(db, queue_item_id, "URL record not found")
                return

            url_to_submit = url_rec.normalized_url
            service_name = item.service
            url_id = item.url_id
            domain_id = url_rec.domain_id

        # Check rate limiter for the target service asynchronously
        limiter = self.limiters.get(service_name)
        if limiter:
            # Wait for available token asynchronously (respect rate limit without blocking thread)
            acquired = await limiter.acquire_async(blocking=True, timeout=15.0)
            if not acquired:
                logger.warning(f"Rate limiter timed out on service {service_name}. Postponing queue item {queue_item_id}.")
                with get_db_context() as db:
                    QueueManager.mark_failed(db, queue_item_id, f"Rate limit timeout on {service_name}")
                return

        # Retrieve submitter
        submitter = get_submitter(service_name)
        if not submitter:
            with get_db_context() as db:
                QueueManager.mark_failed(db, queue_item_id, f"Unknown service: {service_name}")
            return

        # Execute submission
        try:
            result = await submitter.submit(url_to_submit)
        except Exception as e:
            logger.error(f"Submitter raised exception for {url_to_submit}: {e}")
            from backend.app.submitters.base import SubmissionResult
            result = SubmissionResult(
                success=False,
                service=service_name,
                error_message=str(e),
            )

        # Update repository and queue status in atomic transaction
        now = utc_now()
        with get_db_context() as db:
            # Guard against race condition if domain/url was deleted while in-flight
            url_exists = db.query(Url).filter(Url.id == url_id).first()
            if not url_exists:
                logger.info(f"URL id={url_id} was removed during submission. Skipping record.")
                return

            submission_record = Submission(
                url_id=url_id,
                service=service_name,
                submitted_at=result.submitted_at or now,
                completed_at=result.completed_at or now,
                status="success" if result.success else "failed",
                archive_url=result.archive_url,
                archive_id=result.archive_id,
                http_status=result.http_status,
                error_message=result.error_message,
                last_attempted=now,
            )
            db.add(submission_record)

            if domain_id:
                domain = db.query(Domain).filter(Domain.id == domain_id).first()
                if domain:
                    domain.last_submission_at = now

            if result.success:
                QueueManager.mark_completed(db, queue_item_id)
                url_exists.content_changed = False
                self._success_count += 1
            else:
                QueueManager.mark_failed(
                    db,
                    queue_item_id,
                    result.error_message or "Unknown submission failure",
                )
                self._failed_count += 1

            self._processed_count += 1


# Global worker pool singleton
worker_pool = WorkerPool()
