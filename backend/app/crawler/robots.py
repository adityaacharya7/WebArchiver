"""
Robots.txt parser and Sitemap directive extractor.
"""
import re
import logging
import httpx
from urllib.parse import urljoin
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class RobotsParser:
    """Fetches and parses robots.txt to discover sitemaps and crawl rules."""

    def __init__(self, domain: str, timeout: float = 10.0):
        self.domain = domain.lower().strip().rstrip("/")
        if not self.domain.startswith(("http://", "https://")):
            self.base_url = f"https://{self.domain}"
        else:
            self.base_url = self.domain
        self.timeout = timeout
        self.sitemaps: list[str] = []
        self.disallowed_paths: list[str] = []

    async def fetch_and_parse(self) -> dict:
        """
        Fetch robots.txt for the domain and extract sitemaps and rules.
        """
        robots_url = urljoin(self.base_url, "/robots.txt")
        headers = {"User-Agent": settings.CRAWLER_USER_AGENT}

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
                resp = await client.get(robots_url, headers=headers)
                if resp.status_code == 200:
                    self._parse_content(resp.text)
                else:
                    logger.info(f"robots.txt returned status {resp.status_code} for {self.domain}")
        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt for {self.domain}: {e}")

        # Always include default sitemap.xml fallback
        default_sitemap = urljoin(self.base_url, "/sitemap.xml")
        if default_sitemap not in self.sitemaps:
            self.sitemaps.append(default_sitemap)

        return {
            "sitemaps": self.sitemaps,
            "disallowed_paths": self.disallowed_paths,
        }

    def _parse_content(self, text: str):
        """Parse text lines of robots.txt."""
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Check for Sitemap directive (case-insensitive)
            sitemap_match = re.match(r"^sitemap:\s*(.+)$", line, re.IGNORECASE)
            if sitemap_match:
                raw_sitemap = sitemap_match.group(1).strip()
                if raw_sitemap:
                    sitemap_url = urljoin(self.base_url, raw_sitemap)
                    if sitemap_url not in self.sitemaps:
                        self.sitemaps.append(sitemap_url)
                continue

            # Check for Disallow directive
            disallow_match = re.match(r"^disallow:\s*(.+)$", line, re.IGNORECASE)
            if disallow_match:
                disallow_path = disallow_match.group(1).strip()
                if disallow_path and disallow_path != "/":
                    self.disallowed_paths.append(disallow_path)
