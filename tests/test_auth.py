"""
Automated unit and integration tests for Google OAuth 2.0 & Session Authentication.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.db.database import Base, get_db
from backend.app.db.models import User
from backend.app.core.config import settings

# In-memory SQLite DB for testing auth
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


@pytest.fixture
def client():
    return TestClient(app)


def test_auth_config_endpoint(client):
    """Verify /api/auth/config returns status and configuration state."""
    response = client.get("/api/auth/config")
    assert response.status_code == 200
    data = response.json()
    assert "google_enabled" in data
    assert "demo_mode" in data


def test_unauthenticated_me(client):
    """Verify /api/auth/me returns 401 when no session cookie is present."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_demo_login_and_me(client):
    """Verify /api/auth/demo-login sets session cookie and /api/auth/me resolves user."""
    # 1. Trigger demo login
    login_resp = client.post(
        "/api/auth/demo-login",
        json={"name": "Commander Shepard", "email": "shepard@normandy.space"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["authenticated"] is True
    assert login_data["user"]["name"] == "Commander Shepard"
    assert login_data["user"]["email"] == "shepard@normandy.space"
    assert "archiver_session" in login_resp.cookies

    # 2. Call /api/auth/me with session cookie
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["authenticated"] is True
    assert me_data["user"]["name"] == "Commander Shepard"


def test_logout(client):
    """Verify /api/auth/logout clears session token and deletes cookie."""
    # 1. Login first
    client.post("/api/auth/demo-login")
    assert client.get("/api/auth/me").status_code == 200

    # 2. Logout
    logout_resp = client.post("/api/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "success"

    # 3. /api/auth/me should now return 401
    assert client.get("/api/auth/me").status_code == 401


def test_google_login_redirect_when_missing_credentials(client):
    """Verify /api/auth/google/login safely redirects with error flag if keys aren't configured."""
    settings.GOOGLE_CLIENT_ID = None
    settings.GOOGLE_CLIENT_SECRET = None

    response = client.get("/api/auth/google/login", follow_redirects=False)
    assert response.status_code == 303
    assert "auth_error=google_credentials_missing" in response.headers["location"]


def test_google_login_redirect_with_configured_credentials(client):
    """Verify /api/auth/google/login redirects to Google OAuth URL when keys are present."""
    settings.GOOGLE_CLIENT_ID = "mock-google-client-id.apps.googleusercontent.com"
    settings.GOOGLE_CLIENT_SECRET = "mock-client-secret"

    response = client.get("/api/auth/google/login", follow_redirects=False)
    assert response.status_code == 303
    loc = response.headers["location"]
    assert "accounts.google.com/o/oauth2/v2/auth" in loc
    assert "client_id=mock-google-client-id" in loc
    assert "scope=openid+email+profile" in loc or "scope=openid%20email%20profile" in loc

    # Clean up settings
    settings.GOOGLE_CLIENT_ID = None
    settings.GOOGLE_CLIENT_SECRET = None


def test_firebase_config_endpoint(client):
    """Verify /api/auth/firebase-config returns config schema."""
    response = client.get("/api/auth/firebase-config")
    assert response.status_code == 200
    data = response.json()
    assert "configured" in data
    assert "apiKey" in data
    assert "projectId" in data


def test_firebase_session_endpoint(client):
    """Verify /api/auth/firebase/session accepts mock Firebase token, creates user, and logs in."""
    resp = client.post(
        "/api/auth/firebase/session",
        json={
            "id_token": "mock_firebase_token_abc123",
            "email": "sarah.connor@cyberdyne.org",
            "name": "Sarah Connor",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is True
    assert data["user"]["email"] == "sarah.connor@cyberdyne.org"
    assert data["user"]["name"] == "Sarah Connor"
    assert "archiver_session" in resp.cookies

    # Verify session persists on /api/auth/me
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == "sarah.connor@cyberdyne.org"
