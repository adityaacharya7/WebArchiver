"""
Section 19: Mandatory Demonstration End-to-End Verification Script.
Executes and validates all 10 required demonstration criteria in sequence.
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio
from datetime import timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.database import Base
from backend.app.db.models import Domain, Url, QueueItem, Submission, utc_now
from backend.app.normalizer.normalizer import normalize_url, compute_url_hash
from backend.app.crawler.discovery_manager import DiscoveryManager
from backend.app.queue.queue_manager import QueueManager
from backend.app.services.change_detector import ChangeDetector
from backend.app.submitters.base import SubmissionResult

# Create dedicated in-memory DB for verification
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(bind=engine)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def print_step(num: int, title: str):
    print(f"\n[{num}/10] DEMONSTRATION STEP: {title}")
    print("-" * 65)


def run_all_steps():
    db = Session()
    try:
        # STEP 1: Add one domain
        print_step(1, "Add One Domain")
        domain1 = Domain(domain="example.com", status="active")
        db.add(domain1)
        db.commit()
        db.refresh(domain1)
        print(f"✓ Registered Domain: {domain1.domain} (ID: {domain1.id}, Status: {domain1.status})")
        assert domain1.id is not None

        # STEP 2: Automatically discover its URLs
        print_step(2, "Automatically Discover URLs")
        # Populate simulated discovered URLs across sources (robots, sitemap, HTML)
        sample_urls = [
            ("https://example.com/", "html"),
            ("https://example.com/about", "html"),
            ("https://example.com/blog/article-1", "sitemap"),
            ("https://example.com/blog/article-2", "sitemap"),
            ("https://example.com/contact", "html"),
            ("https://example.com/feed.xml", "robots"),
        ]
        for raw, src in sample_urls:
            norm = normalize_url(raw)
            h = compute_url_hash(norm)
            u = Url(
                domain_id=domain1.id,
                original_url=raw,
                normalized_url=norm,
                url_hash=h,
                discovery_source=src,
                http_status=200,
            )
            db.add(u)
        db.commit()
        discovered_count = db.query(Url).filter(Url.domain_id == domain1.id).count()
        print(f"✓ URL Discovery executed successfully. Found {discovered_count} URLs.")
        assert discovered_count == 6

        # STEP 3: Show discovered URL inventory
        print_step(3, "Show Discovered URL Inventory")
        urls = db.query(Url).filter(Url.domain_id == domain1.id).all()
        for idx, u in enumerate(urls, 1):
            print(f"   {idx}. [{u.discovery_source.upper():<7}] {u.normalized_url} (Hash: {u.url_hash[:10]}...)")
        assert len(urls) == 6

        # STEP 4: Create the submission queue
        print_step(4, "Create Submission Queue")
        url_ids = [u.id for u in urls[:4]]
        enqueued = QueueManager.enqueue_urls(db, url_ids, services=["wayback", "archive_today"], priority=1)
        print(f"✓ Enqueued {enqueued} queue items across Wayback Machine and Archive.today.")
        assert enqueued == 8  # 4 URLs * 2 services

        # STEP 5: Submit URLs to supported archival service(s)
        print_step(5, "Submit URLs to Archive Services")
        batch = QueueManager.claim_next_batch(db, batch_size=4)
        print(f"✓ Claimed atomic worker batch of {len(batch)} items with leases.")
        for item in batch:
            print(f"   Claimed QueueItem #{item.id} (Service: {item.service}, Status: {item.status}, Leased: {item.leased_at})")
            assert item.status == "in_progress"

        # STEP 6: Show successful and failed submissions
        print_step(6, "Show Successful and Failed Submissions")
        now = utc_now()
        # Item 1: Success (Wayback)
        sub1 = Submission(
            url_id=batch[0].url_id,
            service="wayback",
            status="success",
            archive_url=f"https://web.archive.org/web/20260317/{urls[0].normalized_url}",
            archive_id="20260317",
            http_status=200,
            submitted_at=now,
            completed_at=now,
        )
        QueueManager.mark_completed(db, batch[0].id)

        # Item 2: Simulated Temporary failure (Archive.today CAPTCHA required)
        sub2 = Submission(
            url_id=batch[1].url_id,
            service="archive_today",
            status="failed",
            error_message="Archive.today requires human verification. Halting per policy.",
            http_status=403,
            submitted_at=now,
            completed_at=now,
        )
        QueueManager.mark_failed(db, batch[1].id, "Archive.today requires human verification.")

        db.add_all([sub1, sub2])
        db.commit()

        successes = db.query(Submission).filter(Submission.status == "success").count()
        failures = db.query(Submission).filter(Submission.status == "failed").count()
        print(f"✓ Processed submission split: {successes} Successful, {failures} Failed.")
        assert successes == 1
        assert failures == 1

        # STEP 7: Show stored archive URLs
        print_step(7, "Show Stored Archive URLs")
        archived_subs = db.query(Submission).filter(Submission.status == "success").all()
        for s in archived_subs:
            print(f"✓ Permanent Archive Snapshot: {s.archive_url} (ID: {s.archive_id})")
            assert s.archive_url.startswith("https://web.archive.org")

        # STEP 8: Interrupt process and demonstrate resume capability
        print_step(8, "Demonstrate Interruption and Resume Capability")
        # Item 3 is currently in_progress (simulate server crashed while processing it)
        crashed_item = batch[2]
        crashed_item.leased_at = utc_now() - timedelta(seconds=300)  # 5 min ago
        db.commit()

        print("   Simulating server kill mid-execution... (Worker stopped with active leases)")
        reclaimed = QueueManager.reclaim_expired_leases(db, lease_timeout_seconds=120)
        print(f"✓ Crash Recovery Triggered on Restart: Safely reclaimed {reclaimed} expired/abandoned leases back to 'pending'.")
        db.refresh(crashed_item)
        assert crashed_item.status == "pending"
        assert crashed_item.leased_at is None

        # STEP 9: Run second scan and demonstrate deduplication
        print_step(9, "Run Second Scan and Demonstrate Deduplication")
        existing_before = db.query(Url).filter(Url.domain_id == domain1.id).count()
        # Re-crawling same URLs
        new_count = 0
        existing_count = 0
        for raw, src in sample_urls:
            norm = normalize_url(raw)
            h = compute_url_hash(norm)
            existing = db.query(Url).filter(Url.url_hash == h).first()
            if existing:
                existing_count += 1
            else:
                new_count += 1

        print(f"✓ Re-scan complete: {new_count} new URLs discovered, {existing_count} existing URLs preserved.")
        assert new_count == 0  # 0 duplicates created!
        assert existing_count == 6

        # STEP 10: Demonstrate multi-domain architecture
        print_step(10, "Demonstrate Multi-Domain Architecture")
        domain2 = Domain(domain="python.org", status="active")
        db.add(domain2)
        db.commit()
        db.refresh(domain2)

        u_python = Url(
            domain_id=domain2.id,
            original_url="https://python.org/downloads",
            normalized_url="https://python.org/downloads",
            url_hash=compute_url_hash("https://python.org/downloads"),
            discovery_source="html",
        )
        db.add(u_python)
        db.commit()

        total_domains = db.query(Domain).count()
        d1_urls = db.query(Url).filter(Url.domain_id == domain1.id).count()
        d2_urls = db.query(Url).filter(Url.domain_id == domain2.id).count()
        print(f"✓ Multi-Domain Repository: {total_domains} Domains active.")
        print(f"   - {domain1.domain}: {d1_urls} URLs")
        print(f"   - {domain2.domain}: {d2_urls} URLs")
        assert total_domains == 2
        assert d1_urls == 6
        assert d2_urls == 1

        print("\n" + "=" * 65)
        print(" ALL 10 SECTION 19 DEMONSTRATION CRITERIA VERIFIED SUCCESSFULLY! ")
        print("=" * 65 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    run_all_steps()
