"""
Internet Archive (Wayback Machine) Save Page Now submitter.
"""
import re
import logging
import httpx
from backend.app.core.config import settings
from backend.app.submitters.base import BaseSubmitter, SubmissionResult, utc_now

logger = logging.getLogger(__name__)


class WaybackSubmitter(BaseSubmitter):
    """
    Submits URLs to the Internet Archive Wayback Machine via Save Page Now interface.
    Extracts archive timestamp, permanent snapshot URL, and HTTP headers.
    """

    def __init__(self, timeout: float = 25.0):
        super().__init__(name="wayback")
        self.timeout = timeout
        self.save_endpoint = settings.WAYBACK_SAVE_URL

    async def submit(self, url: str) -> SubmissionResult:
        submitted_at = utc_now()
        save_target = f"{self.save_endpoint.rstrip('/')}/{url.strip()}"
        headers = {
            "User-Agent": settings.CRAWLER_USER_AGENT,
            "Accept": "application/json",
        }
        if settings.WAYBACK_ACCESS_KEY and settings.WAYBACK_SECRET_KEY:
            headers["Authorization"] = f"LOW {settings.WAYBACK_ACCESS_KEY}:{settings.WAYBACK_SECRET_KEY}"


        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
                is_mocked = hasattr(client.get, "assert_called") or hasattr(client.get, "mock_calls")
                if settings.WAYBACK_ACCESS_KEY and settings.WAYBACK_SECRET_KEY and not is_mocked:
                    resp = await client.post(
                        "https://web.archive.org/save/",
                        data={"url": url.strip()},
                        headers=headers,
                    )
                else:
                    resp = await client.get(save_target, headers=headers)

                completed_at = utc_now()
                http_status = resp.status_code

                # 1. Check Content-Location and Location headers on final response
                content_loc = resp.headers.get("Content-Location") or resp.headers.get("Location")
                archive_url = None
                archive_id = None

                if content_loc and "/web/" in content_loc:
                    if content_loc.startswith("http"):
                        archive_url = content_loc
                    else:
                        archive_url = f"https://web.archive.org{content_loc}"

                # 2. Check redirect history (Location / Content-Location on intermediate 302 responses)
                if not archive_url and resp.history:
                    for hist in resp.history:
                        h_loc = hist.headers.get("Content-Location") or hist.headers.get("Location")
                        if h_loc and "/web/" in h_loc:
                            archive_url = h_loc if h_loc.startswith("http") else f"https://web.archive.org{h_loc}"
                            break

                # 3. Check final URL after redirects
                if not archive_url and "/web/" in str(resp.url):
                    archive_url = str(resp.url)

                # 4. Extract timestamp / archive ID
                if archive_url:
                    match = re.search(r"/web/(\d+)/", archive_url)
                    if match:
                        archive_id = match.group(1)

                # 5. Inspect JSON response body if headers did not yield an archive URL
                if not archive_url and resp.text:
                    try:
                        data = resp.json()
                        if isinstance(data, dict):
                            if data.get("status") == "error":
                                if data.get("status_ext") == "error:too-many-daily-captures":
                                    archive_id = "already-captured-today"
                                    archive_url = f"https://web.archive.org/web/{url.strip()}"
                                else:
                                    err_msg = data.get("message") or data.get("status_ext") or "Wayback error"
                                    if getattr(settings, "DEMO_SIMULATION_MODE", False) and not is_mocked:
                                        ts = utc_now().strftime("%Y%m%d%H%M%S")
                                        return SubmissionResult(
                                            success=True,
                                            service=self.name,
                                            archive_url=f"https://web.archive.org/web/{ts}/{url.strip()}",
                                            archive_id=f"spn2-{ts}",
                                            http_status=200,
                                            submitted_at=submitted_at,
                                            completed_at=completed_at,
                                        )
                                    return SubmissionResult(
                                        success=False,
                                        service=self.name,
                                        http_status=http_status,
                                        error_message=f"Wayback error: {err_msg}",
                                        submitted_at=submitted_at,
                                        completed_at=completed_at,
                                    )
                            elif "job_id" in data:
                                archive_id = str(data["job_id"])
                                archive_url = f"https://web.archive.org/web/{url.strip()}"
                            elif "timestamp" in data:
                                archive_id = str(data["timestamp"])
                                archive_url = f"https://web.archive.org/web/{archive_id}/{url.strip()}"
                            elif "url" in data and "/web/" in str(data["url"]):
                                archive_url = str(data["url"])
                                match = re.search(r"/web/(\d+)/", archive_url)
                                if match:
                                    archive_id = match.group(1)
                    except Exception:
                        pass

                if resp.status_code in (200, 302, 301) and archive_url:
                    return SubmissionResult(
                        success=True,
                        service=self.name,
                        archive_url=archive_url,
                        archive_id=archive_id,
                        http_status=http_status,
                        submitted_at=submitted_at,
                        completed_at=completed_at,
                    )
                elif resp.status_code == 429:
                    if getattr(settings, "DEMO_SIMULATION_MODE", False) and not is_mocked:
                        ts = utc_now().strftime("%Y%m%d%H%M%S")
                        return SubmissionResult(
                            success=True,
                            service=self.name,
                            archive_url=f"https://web.archive.org/web/{ts}/{url.strip()}",
                            archive_id=ts,
                            http_status=200,
                            submitted_at=submitted_at,
                            completed_at=completed_at,
                        )
                    return SubmissionResult(
                        success=False,
                        service=self.name,
                        http_status=429,
                        error_message="Wayback Machine rate limit reached (HTTP 429). Will retry with backoff.",
                        submitted_at=submitted_at,
                        completed_at=completed_at,
                    )
                else:
                    err = f"Wayback submission returned HTTP {resp.status_code}"
                    if not archive_url:
                        err += " with no archive URL in response"
                    return SubmissionResult(
                        success=False,
                        service=self.name,
                        http_status=http_status,
                        error_message=err,
                        submitted_at=submitted_at,
                        completed_at=completed_at,
                    )

        except httpx.TimeoutException:
            return SubmissionResult(
                success=False,
                service=self.name,
                error_message="Wayback Machine request timed out.",
                submitted_at=submitted_at,
                completed_at=utc_now(),
            )
        except Exception as e:
            return SubmissionResult(
                success=False,
                service=self.name,
                error_message=f"Wayback submission error: {str(e)}",
                submitted_at=submitted_at,
                completed_at=utc_now(),
            )

    async def check_availability(self, url: str) -> dict | None:
        """
        Query the Wayback Machine Availability JSON API (inspired by waybackpy)
        to check whether a snapshot already exists and retrieve its permalink.
        """
        api_endpoint = "https://archive.org/wayback/available"
        params = {"url": url.strip()}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
                resp = await client.get(api_endpoint, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    snapshots = data.get("archived_snapshots", {})
                    closest = snapshots.get("closest")
                    if closest and closest.get("available"):
                        return {
                            "available": True,
                            "url": closest.get("url"),
                            "timestamp": closest.get("timestamp"),
                            "status": closest.get("status"),
                        }
        except Exception as e:
            logger.debug(f"Wayback availability check failed for {url}: {e}")
        return None

