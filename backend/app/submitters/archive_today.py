"""
Archive.today / Archive.is defensive submitter.
Strictly adheres to terms: does NOT attempt to bypass CAPTCHAs or security controls.
"""
import re
import logging
import httpx
from bs4 import BeautifulSoup
from backend.app.core.config import settings
from backend.app.submitters.base import BaseSubmitter, SubmissionResult, utc_now

logger = logging.getLogger(__name__)


class ArchiveTodaySubmitter(BaseSubmitter):
    """
    Submits URLs to Archive.today / Archive.ph.
    Extracts short permalinks defensively, and cleanly reports when human verification
    or rate limits are requested without bypassing them.
    """

    def __init__(self, timeout: float = 30.0):
        super().__init__(name="archive_today")
        self.timeout = timeout
        self.submit_endpoint = settings.ARCHIVE_TODAY_SUBMIT_URL

    async def submit(self, url: str) -> SubmissionResult:
        submitted_at = utc_now()
        headers = {
            "User-Agent": settings.CRAWLER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://archive.ph/",
            "Origin": "https://archive.ph",
        }
        data = {"url": url.strip()}

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False, verify=False) as client:
                resp = await client.post(self.submit_endpoint, data=data, headers=headers)
                completed_at = utc_now()

                # Check for 302 Redirect with Location header
                if resp.status_code in (301, 302, 303, 307):
                    location = resp.headers.get("Location")
                    if location:
                        archive_url = location if location.startswith("http") else f"https://archive.ph{location}"
                        archive_id = archive_url.rstrip("/").split("/")[-1]
                        # Validate that the redirect is an actual snapshot link, not a challenge or /submit/
                        if not archive_url.endswith("/submit/") and not any(k in archive_url.lower() for k in ("challenge", "captcha", "turnstile")):
                            if re.match(r"^https?://archive\.(ph|today|is|li|vn|md)/[a-zA-Z0-9]+$", archive_url):
                                return SubmissionResult(
                                    success=True,
                                    service=self.name,
                                    archive_url=archive_url,
                                    archive_id=archive_id,
                                    http_status=resp.status_code,
                                    submitted_at=submitted_at,
                                    completed_at=completed_at,
                                )
                        elif any(k in archive_url.lower() for k in ("challenge", "captcha", "turnstile")):
                            return SubmissionResult(
                                success=False,
                                service=self.name,
                                http_status=resp.status_code,
                                error_message="Archive.today requires human verification (CAPTCHA/anti-automation). Submission paused to respect service policies.",
                                submitted_at=submitted_at,
                                completed_at=completed_at,
                            )

                # Check for Refresh header (used by Archive.today for pending snapshots)
                refresh_hdr = resp.headers.get("Refresh")
                if refresh_hdr and "url=" in refresh_hdr.lower():
                    ref_match = re.search(r"url=(https?://[^\s;]+)", refresh_hdr, re.IGNORECASE)
                    if ref_match:
                        ref_target = ref_match.group(1).strip()
                        if re.match(r"^https?://archive\.(ph|today|is|li|vn|md)/[a-zA-Z0-9]+$", ref_target):
                            archive_id = ref_target.rstrip("/").split("/")[-1]
                            return SubmissionResult(
                                success=True,
                                service=self.name,
                                archive_url=ref_target,
                                archive_id=archive_id,
                                http_status=resp.status_code,
                                submitted_at=submitted_at,
                                completed_at=completed_at,
                            )

                # Check if landed directly on archive page
                final_url = str(resp.url)
                if any(domain in final_url for domain in ("archive.ph/", "archive.today/", "archive.is/")) and "/submit" not in final_url:
                    archive_id = final_url.rstrip("/").split("/")[-1]
                    return SubmissionResult(
                        success=True,
                        service=self.name,
                        archive_url=final_url,
                        archive_id=archive_id,
                        http_status=resp.status_code,
                        submitted_at=submitted_at,
                        completed_at=completed_at,
                    )

                body = resp.text.lower()
                # Check for Cloudflare / CAPTCHA challenge
                if "cf-turnstile" in body or "challenge" in body or "captcha" in body or resp.status_code in (403, 429):
                    return SubmissionResult(
                        success=False,
                        service=self.name,
                        http_status=resp.status_code,
                        error_message="Archive.today requires human verification (CAPTCHA/anti-automation). Submission paused to respect service policies.",
                        submitted_at=submitted_at,
                        completed_at=completed_at,
                    )

                # Inspect HTML for result links
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if re.match(r"^https?://archive\.(ph|today|is|li|vn)/[a-zA-Z0-9]+$", href):
                        archive_id = href.rstrip("/").split("/")[-1]
                        return SubmissionResult(
                            success=True,
                            service=self.name,
                            archive_url=href,
                            archive_id=archive_id,
                            http_status=resp.status_code,
                            submitted_at=submitted_at,
                            completed_at=completed_at,
                        )

                return SubmissionResult(
                    success=False,
                    service=self.name,
                    http_status=resp.status_code,
                    error_message=f"Archive.today response HTTP {resp.status_code} did not contain a valid snapshot link.",
                    submitted_at=submitted_at,
                    completed_at=completed_at,
                )

        except httpx.TimeoutException:
            return SubmissionResult(
                success=False,
                service=self.name,
                error_message="Archive.today request timed out.",
                submitted_at=submitted_at,
                completed_at=utc_now(),
            )
        except Exception as e:
            return SubmissionResult(
                success=False,
                service=self.name,
                error_message=f"Archive.today submission error: {str(e)}",
                submitted_at=submitted_at,
                completed_at=utc_now(),
            )
