"""
Unit tests for queue management: persistent leases, crash recovery, backoff, and priority.
"""
from datetime import timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import Base
from backend.app.db.models import Domain, Url, QueueItem, utc_now
from backend.app.queue.queue_manager import QueueManager
from backend.app.queue.rate_limiter import TokenBucketRateLimiter


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_enqueue_and_deduplication(test_db):
    domain = Domain(domain="testsite.org")
    test_db.add(domain)
    test_db.commit()

    url = Url(
        domain_id=domain.id,
        original_url="https://testsite.org/1",
        normalized_url="https://testsite.org/1",
        url_hash="hash1",
        discovery_source="html",
    )
    test_db.add(url)
    test_db.commit()

    # Enqueue for wayback and archive_today
    added = QueueManager.enqueue_urls(test_db, [url.id], services=["wayback", "archive_today"])
    assert added == 2
    assert test_db.query(QueueItem).count() == 2

    # Enqueueing again for the same services should be deduplicated (0 new added)
    added_again = QueueManager.enqueue_urls(test_db, [url.id], services=["wayback"])
    assert added_again == 0
    assert test_db.query(QueueItem).count() == 2


def test_claim_next_batch_and_leasing(test_db):
    domain = Domain(domain="testsite.org")
    test_db.add(domain)
    test_db.commit()

    url = Url(
        domain_id=domain.id,
        original_url="https://testsite.org/1",
        normalized_url="https://testsite.org/1",
        url_hash="hash1",
        discovery_source="html",
    )
    test_db.add(url)
    test_db.commit()

    QueueManager.enqueue_urls(test_db, [url.id], services=["wayback"])

    # Claim batch
    batch = QueueManager.claim_next_batch(test_db, batch_size=5)
    assert len(batch) == 1
    assert batch[0].status == "in_progress"
    assert batch[0].attempts == 1
    assert batch[0].leased_at is not None

    # Immediate second claim should return empty because item is in_progress
    batch2 = QueueManager.claim_next_batch(test_db, batch_size=5)
    assert len(batch2) == 0


def test_crash_recovery_reclaims_expired_leases(test_db):
    domain = Domain(domain="crash-test.org")
    test_db.add(domain)
    test_db.commit()

    url = Url(
        domain_id=domain.id,
        original_url="https://crash-test.org/page",
        normalized_url="https://crash-test.org/page",
        url_hash="hash_crash",
        discovery_source="html",
    )
    test_db.add(url)
    test_db.commit()

    # Create an item simulate crash: status="in_progress" but leased 5 minutes ago
    old_time = utc_now() - timedelta(seconds=300)
    crashed_item = QueueItem(
        url_id=url.id,
        service="wayback",
        status="in_progress",
        leased_at=old_time,
        attempts=1,
    )
    test_db.add(crashed_item)
    test_db.commit()

    # Reclaim expired leases (threshold 120s)
    reclaimed = QueueManager.reclaim_expired_leases(test_db, lease_timeout_seconds=120)
    assert reclaimed == 1

    test_db.refresh(crashed_item)
    assert crashed_item.status == "pending"
    assert crashed_item.leased_at is None

    # Now verify it can be claimed again!
    new_batch = QueueManager.claim_next_batch(test_db, batch_size=1)
    assert len(new_batch) == 1
    assert new_batch[0].id == crashed_item.id
    assert new_batch[0].attempts == 2


def test_exponential_backoff_and_permanent_failure(test_db):
    domain = Domain(domain="retry-test.org")
    test_db.add(domain)
    test_db.commit()

    url = Url(
        domain_id=domain.id,
        original_url="https://retry-test.org/1",
        normalized_url="https://retry-test.org/1",
        url_hash="hash_retry",
        discovery_source="html",
    )
    test_db.add(url)
    test_db.commit()

    QueueManager.enqueue_urls(test_db, [url.id], services=["wayback"])
    batch = QueueManager.claim_next_batch(test_db, batch_size=1)
    item_id = batch[0].id

    # Fail attempt 1 (max_retries=3, base=10)
    QueueManager.mark_failed(test_db, item_id, "Temporary network timeout", max_retries=3, backoff_base=10)
    item = test_db.query(QueueItem).filter(QueueItem.id == item_id).first()
    assert item.status == "pending"
    assert item.attempts == 1
    assert item.next_retry_at is not None

    # Simulate attempt 2
    item.next_retry_at = utc_now() - timedelta(seconds=1)
    test_db.commit()
    batch = QueueManager.claim_next_batch(test_db, batch_size=1)
    assert len(batch) == 1
    QueueManager.mark_failed(test_db, item_id, "Second error", max_retries=3, backoff_base=10)
    test_db.refresh(item)
    assert item.status == "pending"
    assert item.attempts == 2

    # Simulate attempt 3 -> should become failed_permanent
    item.next_retry_at = utc_now() - timedelta(seconds=1)
    test_db.commit()
    batch = QueueManager.claim_next_batch(test_db, batch_size=1)
    QueueManager.mark_failed(test_db, item_id, "Final fatal error", max_retries=3, backoff_base=10)
    test_db.refresh(item)
    assert item.status == "failed_permanent"
    assert item.attempts == 3
    assert item.last_error == "Final fatal error"

    # Manual retry resets failed_permanent items
    reset_count = QueueManager.retry_permanent_failures(test_db)
    assert reset_count == 1
    test_db.refresh(item)
    assert item.status == "pending"
    assert item.attempts == 0


def test_priority_queueing(test_db):
    domain = Domain(domain="priority-test.org")
    test_db.add(domain)
    test_db.commit()

    url_low = Url(domain_id=domain.id, original_url="https://priority-test.org/low", normalized_url="https://priority-test.org/low", url_hash="h_low", discovery_source="html")
    url_high = Url(domain_id=domain.id, original_url="https://priority-test.org/high", normalized_url="https://priority-test.org/high", url_hash="h_high", discovery_source="html")
    test_db.add_all([url_low, url_high])
    test_db.commit()

    QueueManager.enqueue_urls(test_db, [url_low.id], services=["wayback"], priority=0)
    QueueManager.enqueue_urls(test_db, [url_high.id], services=["wayback"], priority=10)

    # Claim batch of 1: highest priority must come first
    batch = QueueManager.claim_next_batch(test_db, batch_size=1)
    assert len(batch) == 1
    assert batch[0].url_id == url_high.id
    assert batch[0].priority == 10


def test_token_bucket_rate_limiter():
    limiter = TokenBucketRateLimiter(rate_per_minute=120, capacity=2)
    assert limiter.acquire(blocking=False) is True
    assert limiter.acquire(blocking=False) is True
    # 3rd rapid call without sleep should return False
    assert limiter.acquire(blocking=False) is False


@pytest.mark.anyio
async def test_token_bucket_rate_limiter_async():
    limiter = TokenBucketRateLimiter(rate_per_minute=120, capacity=2)
    assert (await limiter.acquire_async(blocking=False)) is True
    assert (await limiter.acquire_async(blocking=False)) is True
    assert (await limiter.acquire_async(blocking=False)) is False
