"""
Unit tests for ChangeDetector, DiffService, and ExportService.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import Base
from backend.app.db.models import Domain, Url, Submission, QueueItem
from backend.app.services.change_detector import ChangeDetector
from backend.app.services.diff_service import DiffService
from backend.app.services.export_service import ExportService


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


def test_change_detector_and_incremental_enqueue(test_db):
    domain = Domain(domain="example.org")
    test_db.add(domain)
    test_db.commit()

    # Url 1: archived
    u1 = Url(domain_id=domain.id, original_url="https://example.org/1", normalized_url="https://example.org/1", url_hash="h1", discovery_source="html")
    # Url 2: unarchived
    u2 = Url(domain_id=domain.id, original_url="https://example.org/2", normalized_url="https://example.org/2", url_hash="h2", discovery_source="html")
    test_db.add_all([u1, u2])
    test_db.commit()

    # Add successful submission for u1
    sub1 = Submission(url_id=u1.id, service="wayback", status="success", archive_url="https://web.archive.org/...")
    test_db.add(sub1)
    test_db.commit()

    # Inspect domain inventory
    inv = ChangeDetector.inspect_domain_inventory(test_db, domain.id)
    assert inv["total_urls"] == 2
    assert inv["archived_urls_count"] == 1
    assert inv["unarchived_urls_count"] == 1
    assert inv["unarchived_url_ids"] == [u2.id]

    # Enqueue incremental (should only enqueue u2)
    res = ChangeDetector.enqueue_incremental(test_db, domain.id, services=["wayback"])
    assert res["items_enqueued"] == 1

    queued = test_db.query(QueueItem).all()
    assert len(queued) == 1
    assert queued[0].url_id == u2.id


def test_diff_service():
    html_v1 = "<html><body><h1>Title</h1><p>Old content</p></body></html>"
    html_v2 = "<html><body><h1>Title</h1><p>New content updated</p></body></html>"

    diff = DiffService.compute_diff(html_v1, html_v2)
    assert diff["is_identical"] is False
    assert diff["additions_count"] > 0
    assert diff["deletions_count"] > 0

    identical_diff = DiffService.compute_diff(html_v1, html_v1)
    assert identical_diff["is_identical"] is True
    assert identical_diff["additions_count"] == 0


def test_export_service_csv_and_json(test_db):
    domain = Domain(domain="export-test.com")
    test_db.add(domain)
    test_db.commit()

    url = Url(domain_id=domain.id, original_url="https://export-test.com/about", normalized_url="https://export-test.com/about", url_hash="hexport", discovery_source="html")
    test_db.add(url)
    test_db.commit()

    sub = Submission(url_id=url.id, service="wayback", status="success", archive_url="https://web.archive.org/...")
    test_db.add(sub)
    test_db.commit()

    # Test CSV export
    csv_data = ExportService.export_csv(test_db, domain.id)
    assert "export-test.com" in csv_data
    assert "https://export-test.com/about" in csv_data
    assert "wayback" in csv_data
    assert "content_hash" in csv_data
    assert "content_changed" in csv_data

    # Test JSON export
    json_data = ExportService.export_json(test_db, domain.id)
    assert "export-test.com" in json_data
    assert "https://export-test.com/about" in json_data
    assert "content_hash" in json_data
    assert "content_changed" in json_data


def test_change_detector_rearchive_modified(test_db):
    domain = Domain(domain="change-test.com")
    test_db.add(domain)
    test_db.commit()

    # Url that was previously archived, but content changed
    u = Url(
        domain_id=domain.id,
        original_url="https://change-test.com/page",
        normalized_url="https://change-test.com/page",
        url_hash="h_change",
        discovery_source="html",
        content_changed=True,
    )
    test_db.add(u)
    test_db.commit()

    # Add prior successful submission
    sub = Submission(url_id=u.id, service="wayback", status="success", archive_url="https://web.archive.org/old")
    test_db.add(sub)
    test_db.commit()

    # In regular incremental mode (unarchived only), u is skipped because it was previously archived
    res_incremental = ChangeDetector.enqueue_incremental(test_db, domain.id, services=["wayback"], force_all=False, rearchive_changed=False)
    assert res_incremental["items_enqueued"] == 0

    # In rearchive_changed mode, u is detected as modified and enqueued!
    res_changed = ChangeDetector.enqueue_incremental(test_db, domain.id, services=["wayback"], force_all=False, rearchive_changed=True)
    assert res_changed["items_enqueued"] == 1
    assert res_changed["mode"] == "rearchive_changed_and_unarchived"

