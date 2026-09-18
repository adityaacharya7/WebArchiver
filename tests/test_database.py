"""
Unit tests for database models, constraints, and relationships.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from backend.app.db.database import Base
from backend.app.db.models import Domain, Url, QueueItem, Submission, Schedule


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_domain_crud_and_to_dict(test_db):
    domain = Domain(domain="example.com", status="active")
    test_db.add(domain)
    test_db.commit()
    test_db.refresh(domain)

    assert domain.id is not None
    assert domain.domain == "example.com"
    data = domain.to_dict()
    assert data["domain"] == "example.com"
    assert data["status"] == "active"
    assert "created_at" in data


def test_domain_unique_constraint(test_db):
    d1 = Domain(domain="testsite.org")
    test_db.add(d1)
    test_db.commit()

    d2 = Domain(domain="testsite.org")
    test_db.add(d2)
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


def test_url_deduplication_hash_constraint(test_db):
    domain = Domain(domain="testsite.org")
    test_db.add(domain)
    test_db.commit()

    url1 = Url(
        domain_id=domain.id,
        original_url="https://testsite.org/page1",
        normalized_url="https://testsite.org/page1",
        url_hash="hash123456",
        discovery_source="html"
    )
    test_db.add(url1)
    test_db.commit()

    # Attempt to insert same hash
    url2 = Url(
        domain_id=domain.id,
        original_url="https://testsite.org/page1?ref=abc",
        normalized_url="https://testsite.org/page1",
        url_hash="hash123456",
        discovery_source="sitemap"
    )
    test_db.add(url2)
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


def test_cascade_delete(test_db):
    domain = Domain(domain="cascade-test.org")
    test_db.add(domain)
    test_db.commit()

    url = Url(
        domain_id=domain.id,
        original_url="https://cascade-test.org/hello",
        normalized_url="https://cascade-test.org/hello",
        url_hash="hash_cascade_1",
        discovery_source="html"
    )
    test_db.add(url)
    test_db.commit()

    q_item = QueueItem(url_id=url.id, service="wayback", status="pending")
    sub = Submission(url_id=url.id, service="wayback", status="success", archive_url="https://web.archive.org/...")
    test_db.add_all([q_item, sub])
    test_db.commit()

    # Verify rows exist
    assert test_db.query(Url).count() == 1
    assert test_db.query(QueueItem).count() == 1
    assert test_db.query(Submission).count() == 1

    # Delete domain -> cascade should delete Url, QueueItem, and Submission
    test_db.delete(domain)
    test_db.commit()

    assert test_db.query(Url).count() == 0
    assert test_db.query(QueueItem).count() == 0
    assert test_db.query(Submission).count() == 0
