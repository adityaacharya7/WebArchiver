"""
XML Sitemap and Sitemap Index parser with recursive index traversal.
"""
import logging
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
import httpx
from backend.app.core.config import settings
from backend.app.normalizer.normalizer import (
    normalize_url,
    is_valid_crawl_url,
    is_same_domain,
)

logger = logging.getLogger(__name__)


class SitemapParser:
    """Parses standard sitemap.xml and recursive sitemap indexes."""

    def __init__(self, target_domain: str, timeout: float = 12.0, max_urls: int = 2000, allow_external: bool = False):
        self.target_domain = target_domain
        self.timeout = timeout
        self.max_urls = max_urls
        self.allow_external = allow_external
        self.visited_sitemaps: set[str] = set()

    async def parse_sitemap(self, sitemap_url: str) -> list[dict]:
        """
        Fetch and parse a sitemap or sitemap index URL.
        Returns a list of dicts: {"url": str, "source": "sitemap"}
        """
        discovered: list[dict] = []
        await self._parse_recursive(sitemap_url, discovered, depth=0)
        return discovered

    async def _parse_recursive(self, sitemap_url: str, results: list[dict], depth: int):
        if depth > 2 or len(results) >= self.max_urls:
            return
        if sitemap_url in self.visited_sitemaps:
            return

        self.visited_sitemaps.add(sitemap_url)
        headers = {"User-Agent": settings.CRAWLER_USER_AGENT}

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
                resp = await client.get(sitemap_url, headers=headers)
                if resp.status_code != 200 or not resp.content:
                    return

                content = resp.content
                # Handle gzipped sitemaps (.xml.gz)
                if content.startswith(b"\x1f\x8b") or sitemap_url.lower().endswith(".gz"):
                    try:
                        import gzip
                        content = gzip.decompress(content)
                    except Exception as gz_err:
                        logger.debug(f"Failed to decompress gzip sitemap {sitemap_url}: {gz_err}")

                # Strip namespace prefixes for easier traversal
                try:
                    root = ET.fromstring(content)
                except ET.ParseError as e:
                    logger.debug(f"Failed to parse sitemap XML from {sitemap_url}: {e}")
                    return

                # Check if it is a sitemapindex
                tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

                if tag == "sitemapindex":
                    # Iterate sub-sitemaps
                    for sitemap_elem in root:
                        for child in sitemap_elem:
                            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                            if child_tag == "loc" and child.text:
                                sub_sitemap_url = urljoin(sitemap_url, child.text.strip())
                                await self._parse_recursive(sub_sitemap_url, results, depth + 1)
                                if len(results) >= self.max_urls:
                                    return

                elif tag == "urlset":
                    # Iterate URLs
                    for url_elem in root:
                        loc_url = None
                        lastmod = None
                        for child in url_elem:
                            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                            if child_tag == "loc" and child.text:
                                loc_url = urljoin(sitemap_url, child.text.strip())
                            elif child_tag == "lastmod" and child.text:
                                lastmod = child.text.strip()

                        if loc_url and is_valid_crawl_url(loc_url) and (self.allow_external or is_same_domain(loc_url, self.target_domain)):
                            norm_url = normalize_url(loc_url)
                            if norm_url:
                                results.append({
                                    "original_url": loc_url,
                                    "normalized_url": norm_url,
                                    "source": "sitemap",
                                    "last_modified": lastmod,
                                })
                        if len(results) >= self.max_urls:
                            return

        except Exception as e:
            logger.warning(f"Error reading sitemap {sitemap_url}: {e}")
