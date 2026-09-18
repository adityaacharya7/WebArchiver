"""
Asynchronous HTML breadth-first crawler with depth and page control.
"""
import asyncio
import logging
from collections import deque
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

from backend.app.core.config import settings
from backend.app.normalizer.normalizer import (
    normalize_url,
    compute_url_hash,
    compute_content_hash,
    is_valid_crawl_url,
    is_same_domain,
)

logger = logging.getLogger(__name__)


class HtmlCrawler:
    """
    Crawls HTML pages breadth-first within the configured domain boundary.
    Extracts hyperlinks, canonical links, pagination, records HTTP status,
    and identifies redirects.
    """

    def __init__(
        self,
        domain: str,
        start_urls: list[str] | None = None,
        max_depth: int = 3,
        max_pages: int = 500,
        concurrency: int = 5,
        timeout: float = 12.0,
        allow_external: bool = False,
    ):
        self.domain = domain.lower().strip().rstrip("/")
        if not self.domain.startswith(("http://", "https://")):
            self.base_url = f"https://{self.domain}"
        else:
            self.base_url = self.domain

        self.start_urls = start_urls or [self.base_url]
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.concurrency = concurrency
        self.timeout = timeout
        self.allow_external = allow_external

        self.visited_hashes: set[str] = set()
        self.discovered_urls: dict[str, dict] = {}  # url_hash -> metadata dict
        self.queue: deque[tuple[str, int]] = deque()  # (url, current_depth)
        self.semaphore = asyncio.Semaphore(concurrency)

    async def crawl(self) -> list[dict]:
        """
        Execute the crawl and return all discovered URLs and their page metadata.
        """
        # Seed the queue
        for url in self.start_urls:
            norm = normalize_url(url)
            if norm:
                h = compute_url_hash(norm)
                self.queue.append((norm, 0))
                self.visited_hashes.add(h)

        headers = {
            "User-Agent": settings.CRAWLER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
            while self.queue and len(self.discovered_urls) < self.max_pages:
                batch: list[tuple[str, int]] = []
                while self.queue and len(batch) < self.concurrency and (len(self.discovered_urls) + len(batch)) < self.max_pages:
                    batch.append(self.queue.popleft())

                if not batch:
                    break

                tasks = [self._process_page(client, url, depth, headers) for url, depth in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

        return list(self.discovered_urls.values())

    async def _process_page(self, client: httpx.AsyncClient, current_url: str, depth: int, headers: dict):
        async with self.semaphore:
            norm_url = normalize_url(current_url)
            if not norm_url:
                return

            url_hash = compute_url_hash(norm_url)

            # Metadata container
            item = {
                "original_url": current_url,
                "normalized_url": norm_url,
                "url_hash": url_hash,
                "source": "html",
                "http_status": None,
                "content_hash": None,
                "is_redirect": False,
                "resolved_url": norm_url,
                "discovered_links": [],
            }

            try:
                resp = await client.get(current_url, headers=headers)
                item["http_status"] = resp.status_code

                # Detect redirects
                if str(resp.url) != current_url:
                    item["is_redirect"] = True
                    item["resolved_url"] = str(resp.url)

                content_type = resp.headers.get("content-type", "").lower()
                if "text/html" in content_type or "xhtml" in content_type:
                    html_text = resp.text
                    item["content_hash"] = compute_content_hash(html_text)

                    # Only extract links if depth limit not reached
                    if depth < self.max_depth:
                        links = self._extract_links(html_text, str(resp.url))
                        for raw_link in links:
                            if is_valid_crawl_url(raw_link) and (self.allow_external or is_same_domain(raw_link, self.domain)):
                                link_norm = normalize_url(raw_link, base_url=str(resp.url))
                                if link_norm:
                                    link_hash = compute_url_hash(link_norm)
                                    item["discovered_links"].append(link_norm)
                                    if link_hash not in self.visited_hashes:
                                        self.visited_hashes.add(link_hash)
                                        self.queue.append((link_norm, depth + 1))

            except httpx.TimeoutException:
                logger.debug(f"Timeout crawling {current_url}")
                item["http_status"] = 504
            except httpx.ConnectError as e:
                logger.debug(f"Connection/DNS error crawling {current_url}: {e}")
                item["http_status"] = 502
            except httpx.HTTPStatusError as e:
                logger.debug(f"HTTP status error crawling {current_url}: {e}")
                item["http_status"] = e.response.status_code
            except httpx.HTTPError as e:
                logger.debug(f"HTTP error on {current_url}: {e}")
                item["http_status"] = getattr(getattr(e, "response", None), "status_code", 599)
            except Exception as e:
                logger.debug(f"Unexpected error crawling {current_url}: {e}")
                item["http_status"] = 599

            self.discovered_urls[url_hash] = item

    def _extract_links(self, html_text: str, base_url: str) -> set[str]:
        """Extract all outgoing href, canonical, and pagination links."""
        found: set[str] = set()
        try:
            soup = BeautifulSoup(html_text, "html.parser")

            # Check for HTML <base href="..."> tag
            effective_base = base_url
            base_tag = soup.find("base", href=True)
            if base_tag and base_tag.get("href"):
                base_href = base_tag["href"].strip()
                if base_href:
                    effective_base = urljoin(base_url, base_href)

            # 1. <a> tags
            for a in soup.find_all("a", href=True):
                href = a["href"].replace("\r", "").replace("\n", "").strip()
                if href and not href.startswith(("#", "javascript:", "mailto:", "tel:", "sms:", "data:")):
                    found.add(urljoin(effective_base, href))

            # 2. Canonical tag
            canonical = soup.find("link", rel="canonical")
            if canonical and canonical.get("href"):
                c_href = canonical["href"].replace("\r", "").replace("\n", "").strip()
                if c_href:
                    found.add(urljoin(effective_base, c_href))

            # 3. Pagination links (rel="next", rel="prev")
            for page_link in soup.find_all("link", rel=["next", "prev"]):
                if page_link.get("href"):
                    p_href = page_link["href"].replace("\r", "").replace("\n", "").strip()
                    if p_href:
                        found.add(urljoin(effective_base, p_href))

        except Exception as e:
            logger.debug(f"Failed to parse links with BeautifulSoup: {e}")

        return found
