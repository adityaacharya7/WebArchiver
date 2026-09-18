"""
Integration tests for FastAPI REST API endpoints and dashboard routes.
"""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.database import Base, engine, get_db
from backend.app.db.models import Domain, Url, Submission, QueueItem
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set up test database with StaticPool for in-memory SQLite persistence across threads
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_render_index_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Website Archive Submitter" in resp.text


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_domain_crud_api(client):
    # Add domain
    resp = client.post("/api/domains", json={"domain": "test-domain.org"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "created"
    assert data["domain"]["domain"] == "test-domain.org"
    domain_id = data["domain"]["id"]

    # List domains
    list_resp = client.get("/api/domains")
    assert list_resp.status_code == 200
    domains = list_resp.json()
    assert len(domains) == 1
    assert domains[0]["domain"] == "test-domain.org"

    # Delete domain
    del_resp = client.delete(f"/api/domains/{domain_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"


def test_queue_control_api(client):
    # Pause queue
    resp = client.post("/api/queue/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"

    # Resume queue
    resp = client.post("/api/queue/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "resumed"


def test_export_api(client):
    # Add test domain
    client.post("/api/domains", json={"domain": "export-demo.com"})

    # Export CSV
    csv_resp = client.get("/api/export?format=csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]

    # Export JSON
    json_resp = client.get("/api/export?format=json")
    assert json_resp.status_code == 200
    assert "application/json" in json_resp.headers["content-type"]


def test_diff_api(client):
    payload = {
        "text_a": "Initial version",
        "text_b": "Modified version updated",
    }
    resp = client.post("/api/bonus/diff", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_identical"] is False
    assert data["additions_count"] > 0


def test_repository_filter_api(client):
    db = TestingSessionLocal()
    try:
        d = Domain(domain="filter-demo.org")
        db.add(d)
        db.commit()

        u1 = Url(domain_id=d.id, original_url="https://filter-demo.org/1", normalized_url="https://filter-demo.org/1", url_hash="h_f1", discovery_source="html")
        u2 = Url(domain_id=d.id, original_url="https://filter-demo.org/2", normalized_url="https://filter-demo.org/2", url_hash="h_f2", discovery_source="sitemap")
        db.add_all([u1, u2])
        db.commit()

        sub1 = Submission(url_id=u1.id, service="wayback", status="success", archive_url="https://web.archive.org/...")
        q2 = QueueItem(url_id=u2.id, service="archive_today", status="pending")
        db.add_all([sub1, q2])
        db.commit()
    finally:
        db.close()

    # Filter by service + status (wayback + success)
    resp = client.get("/api/repository/urls?service=wayback&status=success")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["normalized_url"] == "https://filter-demo.org/1"

    # Filter by service + status (archive_today + pending)
    resp2 = client.get("/api/repository/urls?service=archive_today&status=pending")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] == 1
    assert data2["items"][0]["normalized_url"] == "https://filter-demo.org/2"

    # Filter by source (sitemap)
    resp3 = client.get("/api/repository/urls?source=sitemap")
    assert resp3.status_code == 200
    assert resp3.json()["total"] == 1

    # Filter by status (unarchived) - u2 has never been submitted
    resp4 = client.get("/api/repository/urls?status=unarchived")
    assert resp4.status_code == 200
    assert any(it["normalized_url"] == "https://filter-demo.org/2" for it in resp4.json()["items"])


def test_bonus_schedule_api(client):
    # Add domain first
    d_resp = client.post("/api/domains", json={"domain": "sched-test.com"})
    d_id = d_resp.json()["domain"]["id"]

    # Schedule recurring scan
    s_resp = client.post("/api/bonus/schedule", json={"domain_id": d_id, "interval_minutes": 120})
    assert s_resp.status_code == 200
    s_data = s_resp.json()
    assert s_data["status"] == "scheduled"
    assert s_data["schedule"]["next_run_at"] is not None
    assert s_data["schedule"]["interval_minutes"] == 120


def test_enqueue_all_domains_api(client):
    # Create two domains with URLs
    d1 = client.post("/api/domains", json={"domain": "multi1.org"}).json()["domain"]["id"]
    d2 = client.post("/api/domains", json={"domain": "multi2.org"}).json()["domain"]["id"]

    db = TestingSessionLocal()
    try:
        u1 = Url(domain_id=d1, original_url="https://multi1.org/p", normalized_url="https://multi1.org/p", url_hash="h_m1", discovery_source="html")
        u2 = Url(domain_id=d2, original_url="https://multi2.org/p", normalized_url="https://multi2.org/p", url_hash="h_m2", discovery_source="html")
        db.add_all([u1, u2])
        db.commit()
    finally:
        db.close()

    # Call enqueue-all
    resp = client.post("/api/domains/enqueue-all", json={"services": ["wayback"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "enqueued_all"
    assert data["total_items_enqueued"] >= 2


def test_repository_domain_search_and_is_queued_api(client):
    d_resp = client.post("/api/domains", json={"domain": "search-domain.org"})
    domain_id = d_resp.json()["domain"]["id"]

    db = TestingSessionLocal()
    try:
        u = Url(domain_id=domain_id, original_url="https://search-domain.org/about", normalized_url="https://search-domain.org/about", url_hash="h_search", discovery_source="html")
        db.add(u)
        db.commit()
        q = QueueItem(url_id=u.id, service="wayback", status="pending")
        db.add(q)
        db.commit()
    finally:
        db.close()

    # Search by domain string in query parameter
    resp = client.get("/api/repository/urls?search=search-domain.org")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["domain_name"] == "search-domain.org"
    assert data["items"][0]["is_queued"] is True


def test_favicon_api(client):
    resp = client.get("/favicon.ico")
    assert resp.status_code == 204


def test_bonus_schedule_delete_api(client):
    # Add domain
    d_resp = client.post("/api/domains", json={"domain": "delete-sched.org"})
    d_id = d_resp.json()["domain"]["id"]

    # Schedule scan
    s_resp = client.post("/api/bonus/schedule", json={"domain_id": d_id, "interval_minutes": 60})
    assert s_resp.status_code == 200
    s_id = s_resp.json()["schedule"]["id"]

    # Delete schedule
    del_resp = client.delete(f"/api/bonus/schedule/{s_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # Second delete returns 404
    del_resp404 = client.delete(f"/api/bonus/schedule/{s_id}")
    assert del_resp404.status_code == 404


def test_enqueue_mode_all_api(client):
    d_resp = client.post("/api/domains", json={"domain": "mode-all.org"})
    d_id = d_resp.json()["domain"]["id"]

    db = TestingSessionLocal()
    try:
        u = Url(domain_id=d_id, original_url="https://mode-all.org/page", normalized_url="https://mode-all.org/page", url_hash="h_mode_all", discovery_source="html")
        db.add(u)
        db.commit()
    finally:
        db.close()

    # Single domain enqueue with mode: "all"
    res = client.post(f"/api/domains/{d_id}/enqueue", json={"mode": "all", "services": ["wayback"]})
    assert res.status_code == 200
    assert res.json()["mode"] == "force_all"
    assert res.json()["items_enqueued"] == 1


def test_url_wayback_availability_api(client, monkeypatch):
    from unittest.mock import AsyncMock
    d_resp = client.post("/api/domains", json={"domain": "avail-demo.org"})
    d_id = d_resp.json()["domain"]["id"]

    db = TestingSessionLocal()
    try:
        u = Url(domain_id=d_id, original_url="https://avail-demo.org/item", normalized_url="https://avail-demo.org/item", url_hash="h_avail", discovery_source="html")
        db.add(u)
        db.commit()
        url_id = u.id
    finally:
        db.close()

    mock_avail = AsyncMock(return_value={
        "available": True,
        "url": "https://web.archive.org/web/20260101/https://avail-demo.org/item",
        "timestamp": "20260101",
        "status": "200",
    })
    monkeypatch.setattr("backend.app.submitters.wayback.WaybackSubmitter.check_availability", mock_avail)

    res = client.get(f"/api/urls/{url_id}/availability")
    assert res.status_code == 200
    data = res.json()
    assert data["availability"]["available"] is True
    assert "20260101" in data["availability"]["timestamp"]





