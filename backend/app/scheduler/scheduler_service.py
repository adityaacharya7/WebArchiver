"""
Scheduled recurring discovery and backup manager using APScheduler (Bonus Challenge).
"""
import asyncio
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.app.db.database import get_db_context
from backend.app.db.models import Schedule, Domain, utc_now
from backend.app.crawler.discovery_manager import DiscoveryManager
from backend.app.services.change_detector import ChangeDetector

logger = logging.getLogger(__name__)


class DomainScheduler:
    """Manages recurring automated crawl & archival jobs."""

    def __init__(self):
        self.scheduler = BackgroundScheduler(daemon=True)
        self._started = False

    def start(self):
        """Start the background scheduler."""
        if not self._started:
            self.scheduler.start()
            self._started = True
            logger.info("DomainScheduler started.")
            self._sync_all_jobs()

    def stop(self):
        """Shutdown background scheduler."""
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("DomainScheduler stopped.")

    def _sync_all_jobs(self):
        """Load and schedule all active domain schedules from the database."""
        with get_db_context() as db:
            schedules = db.query(Schedule).filter(Schedule.is_active == True).all()  # noqa: E712
            for sched in schedules:
                self.add_or_update_schedule(sched.domain_id, sched.interval_minutes)

    def add_or_update_schedule(self, domain_id: int, interval_minutes: int):
        """Register or update an interval recurring job for a domain."""
        job_id = f"domain_crawl_{domain_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        trigger = IntervalTrigger(minutes=interval_minutes)
        self.scheduler.add_job(
            func=self._execute_scheduled_scan,
            trigger=trigger,
            id=job_id,
            args=[domain_id],
            replace_existing=True,
        )
        logger.info(f"Registered recurring scan for domain_id={domain_id} every {interval_minutes}m")

    def remove_schedule(self, domain_id: int):
        """Remove recurring job for a domain."""
        job_id = f"domain_crawl_{domain_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled job for domain_id={domain_id}")

    @staticmethod
    def _execute_scheduled_scan(domain_id: int):
        """Executes scheduled discovery and automatic incremental archival enqueuing."""
        logger.info(f"Triggering automated scheduled scan for domain_id={domain_id}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with get_db_context() as db:
                domain = db.query(Domain).filter(Domain.id == domain_id).first()
                if not domain or domain.status == "paused":
                    logger.info(f"Domain {domain_id} not found or paused. Skipping scheduled scan.")
                    return

                # Run discovery
                manager = DiscoveryManager(domain.domain)
                loop.run_until_complete(manager.run_discovery(db))

                # Automatically enqueue newly discovered/unarchived URLs
                ChangeDetector.enqueue_incremental(db, domain_id=domain.id, services=["wayback"])

                # Update schedule metadata
                sched = db.query(Schedule).filter(Schedule.domain_id == domain_id).first()
                if sched:
                    sched.last_run_at = utc_now()
                    sched.next_run_at = utc_now() + timedelta(minutes=sched.interval_minutes)

        except Exception as e:
            logger.error(f"Scheduled scan failed for domain_id={domain_id}: {e}", exc_info=True)
        finally:
            loop.close()


scheduler_service = DomainScheduler()
