"""
RSS and Atom feed autodiscovery and parser.
"""
import logging
import xml.etree.ElementTree as ET
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from backend.app.core.config import settings
from backend.app.normalizer.normalizer import (
    normalize_url,
    is_valid_crawl_url,
    is_same_domain,
)

logger = logging.getLogger(__name__)


class FeedParser:
    """Discovers and parses RSS and Atom feeds linked from pages."""

    def __init__(self, target_domain: str, timeout: float = 10.0, allow_external: bool = False):
        self.target_domain = target_domain
        self.timeout = timeout
        self.allow_external = allow_external

    def extract_feed_links(self, html_content: str, base_url: str) -> list[str]:
        """Extract RSS and Atom feed links from HTML head."""
        feed_urls: list[str] = []
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            for link in soup.find_all("link", rel="alternate"):
                feed_type = (link.get("type") or "").lower()
                href = link.get("href")
                if href and ("rss" in feed_type or "atom" in feed_type or "xml" in feed_type):
                    full_url = urljoin(base_url, href)
                    if full_url not in feed_urls:
                        feed_urls.append(full_url)
        except Exception as e:
            logger.debug(f"Feed link extraction failed: {e}")
        return feed_urls

    async def parse_feed(self, feed_url: str) -> list[dict]:
        """Fetch and parse an RSS or Atom feed for article/entry URLs."""
        discovered: list[dict] = []
        headers = {"User-Agent": settings.CRAWLER_USER_AGENT}

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
                resp = await client.get(feed_url, headers=headers)
                if resp.status_code != 200 or not resp.content:
                    return discovered

                root = ET.fromstring(resp.content)
                tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

                # RSS 2.0 (<rss><channel><item><link>...</link></item>...)
                if tag in ("rss", "rdf"):
                    for item in root.iter("item"):
                        link_elem = item.find("link")
                        if link_elem is not None and link_elem.text:
                            raw_url = link_elem.text.strip()
                            self._add_if_valid(raw_url, discovered, base_url=feed_url)

                # Atom feed (<feed><entry><link href="..." />...)
                elif tag == "feed":
                    entries = [
                        elem for elem in root.iter() if elem.tag.split("}")[-1] == "entry"
                    ]
                    for entry in entries:
                        links = [
                            elem for elem in entry.iter() if elem.tag.split("}")[-1] == "link"
                        ]
                        for link in links:
                            rel = link.attrib.get("rel", "alternate")
                            if rel in ("alternate", ""):
                                raw_url = link.attrib.get("href") or (link.text.strip() if link.text else None)
                                if raw_url:
                                    self._add_if_valid(raw_url, discovered, base_url=feed_url)

        except Exception as e:
            logger.debug(f"Failed to parse feed {feed_url}: {e}")

        return discovered

    def _add_if_valid(self, raw_url: str, results: list[dict], base_url: str | None = None):
        if not raw_url:
            return
        if base_url:
            raw_url = urljoin(base_url, raw_url)

        if is_valid_crawl_url(raw_url) and (self.allow_external or is_same_domain(raw_url, self.target_domain)):
            norm_url = normalize_url(raw_url)
            if norm_url:
                results.append({
                    "original_url": raw_url,
                    "normalized_url": norm_url,
                    "source": "feed",
                })
