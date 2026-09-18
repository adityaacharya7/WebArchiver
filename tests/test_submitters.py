"""
Unit tests for archive submitters: Wayback, Archive.today, Ghostarchive, and registry.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.app.submitters.wayback import WaybackSubmitter
from backend.app.submitters.archive_today import ArchiveTodaySubmitter
from backend.app.submitters.ghostarchive import GhostarchiveSubmitter
from backend.app.submitters.registry import get_submitter, list_available_services


def test_submitter_registry():
    services = list_available_services()
    assert "wayback" in services
    assert "archive_today" in services
    assert "ghostarchive" in services

    assert isinstance(get_submitter("wayback"), WaybackSubmitter)
    assert isinstance(get_submitter("archive_today"), ArchiveTodaySubmitter)
    assert isinstance(get_submitter("ghostarchive"), GhostarchiveSubmitter)
    assert get_submitter("non_existent") is None


@pytest.mark.anyio
async def test_wayback_submitter_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {
        "Content-Location": "/web/20260317150000/https://example.com",
    }
    mock_resp.url = "https://web.archive.org/web/20260317150000/https://example.com"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        submitter = WaybackSubmitter()
        res = await submitter.submit("https://example.com")

        assert res.success is True
        assert res.service == "wayback"
        assert res.archive_url == "https://web.archive.org/web/20260317150000/https://example.com"
        assert res.archive_id == "20260317150000"
        assert res.http_status == 200


@pytest.mark.anyio
async def test_wayback_submitter_rate_limited():
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {}
    mock_resp.url = "https://web.archive.org/save/https://example.com"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        submitter = WaybackSubmitter()
        res = await submitter.submit("https://example.com")

        assert res.success is False
        assert res.http_status == 429
        assert "rate limit" in res.error_message.lower()


@pytest.mark.anyio
async def test_archive_today_submitter_redirect():
    mock_resp = MagicMock()
    mock_resp.status_code = 302
    mock_resp.headers = {"Location": "https://archive.ph/abc12"}
    mock_resp.url = "https://archive.ph/submit/"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        submitter = ArchiveTodaySubmitter()
        res = await submitter.submit("https://example.com")

        assert res.success is True
        assert res.service == "archive_today"
        assert res.archive_url == "https://archive.ph/abc12"
        assert res.archive_id == "abc12"


@pytest.mark.anyio
async def test_archive_today_anti_automation_handled():
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.headers = {}
    mock_resp.text = "<html><body>Please solve the captcha: cf-turnstile</body></html>"
    mock_resp.url = "https://archive.ph/submit/"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        submitter = ArchiveTodaySubmitter()
        res = await submitter.submit("https://example.com")

        assert res.success is False
        assert "captcha" in res.error_message.lower() or "human verification" in res.error_message.lower()


@pytest.mark.anyio
async def test_ghostarchive_submitter_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://ghostarchive.org/archive/gh12345"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        submitter = GhostarchiveSubmitter()
        res = await submitter.submit("https://example.com")

        assert res.success is True
        assert res.service == "ghostarchive"
        assert res.archive_url == "https://ghostarchive.org/archive/gh12345"
        assert res.archive_id == "gh12345"


@pytest.mark.anyio
async def test_wayback_submitter_json_body():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.text = '{"timestamp": "20260317220000", "url": "https://example.com"}'
    mock_resp.json.return_value = {"timestamp": "20260317220000", "url": "https://example.com"}
    mock_resp.url = "https://web.archive.org/save/https://example.com"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        submitter = WaybackSubmitter()
        res = await submitter.submit("https://example.com")

        assert res.success is True
        assert "20260317220000" in res.archive_url
        assert res.archive_id == "20260317220000"


@pytest.mark.anyio
async def test_archive_today_refresh_header():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Refresh": "0;url=https://archive.ph/refresh123"}
    mock_resp.url = "https://archive.ph/submit/"
    mock_resp.text = "<html><body>Redirecting...</body></html>"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        submitter = ArchiveTodaySubmitter()
        res = await submitter.submit("https://example.com")

        assert res.success is True
        assert res.archive_url == "https://archive.ph/refresh123"
        assert res.archive_id == "refresh123"
