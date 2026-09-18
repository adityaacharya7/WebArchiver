"""
Unified Discovery Manager combining Robots.txt, Sitemaps, Feeds, and HTML Crawling.
"""
import time
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.crawler.robots import RobotsParser
from backend.app.crawler.sitemap import SitemapParser
from backend.app.crawler.feeds import FeedParser
from backend.app.crawler.html_crawler import HtmlCrawler
from backend.app.db.models import Domain, Url, utc_now
from backend.app.normalizer.normalizer import (
    clean_domain_name,
    normalize_url,
    compute_url_hash,
)

logger = logging.getLogger(__name__)


class DiscoveryManager:
    """
    Coordinates multi-strategy discovery for a domain and persists
    discovered URLs into the repository.
    """

    def __init__(
        self,
        domain_name: str,
        max_depth: int = 3,
        max_pages: int = 500,
        enable_sitemaps: bool = True,
        enable_feeds: bool = True,
        allow_external: bool = False,
    ):
        self.raw_input = domain_name
        self.domain_clean = clean_domain_name(domain_name)
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.enable_sitemaps = enable_sitemaps
        self.enable_feeds = enable_feeds
        self.allow_external = allow_external

    async def run_discovery(self, db: Session) -> dict:
        """
        Execute discovery across all sources and record in database.
        Returns a summary report.
        """
        start_time = time.time()
        if not self.domain_clean:
            raise ValueError(f"Invalid domain name: {self.raw_input}")

        # Ensure domain exists in database
        domain_record = db.query(Domain).filter(Domain.domain == self.domain_clean).first()
        if not domain_record:
            domain_record = Domain(domain=self.domain_clean, status="active")
            db.add(domain_record)
            db.commit()
            db.refresh(domain_record)

        domain_id = domain_record.id
        discovered_map: dict[str, dict] = {}  # url_hash -> URL record dict
        source_counts = {"sitemap": 0, "html": 0, "feed": 0, "robots": 0}

        # 1. Robots.txt and Sitemap Discovery
        sitemap_urls: list[str] = []
        if self.enable_sitemaps:
            robots_parser = RobotsParser(self.domain_clean)
            robots_data = await robots_parser.fetch_and_parse()
            sitemap_urls.extend(robots_data.get("sitemaps", []))

            # 2. Parse Sitemaps
            sitemap_parser = SitemapParser(self.domain_clean, max_urls=self.max_pages, allow_external=self.allow_external)
            for sm_url in sitemap_urls:
                sm_results = await sitemap_parser.parse_sitemap(sm_url)
                for item in sm_results:
                    norm = item["normalized_url"]
                    h = compute_url_hash(norm)
                    if h not in discovered_map:
                        discovered_map[h] = {
                            "original_url": item["original_url"],
                            "normalized_url": norm,
                            "url_hash": h,
                            "source": "sitemap",
                            "http_status": None,
                            "content_hash": None,
                            "is_redirect": False,
                            "resolved_url": norm,
                        }
                        source_counts["sitemap"] += 1

        # 3. HTML Crawling (BFS)
        start_urls = [f"https://{self.domain_clean}", f"http://{self.domain_clean}"]
        # Seed crawl with top sitemap URLs if available to accelerate discovery
        if discovered_map:
            seed_limit = 10
            for item in list(discovered_map.values())[:seed_limit]:
                if item["normalized_url"] not in start_urls:
                    start_urls.append(item["normalized_url"])

        html_crawler = HtmlCrawler(
            domain=self.domain_clean,
            start_urls=start_urls,
            max_depth=self.max_depth,
            max_pages=self.max_pages,
            allow_external=self.allow_external,
        )
        html_results = await html_crawler.crawl()

        for item in html_results:
            h = item["url_hash"]
            if h not in discovered_map:
                discovered_map[h] = item
                source_counts["html"] += 1
            else:
                # Update with crawled HTTP status and content hash
                discovered_map[h]["http_status"] = item["http_status"]
                discovered_map[h]["content_hash"] = item["content_hash"]
                discovered_map[h]["is_redirect"] = item["is_redirect"]
                discovered_map[h]["resolved_url"] = item["resolved_url"]

        # 4. RSS/Atom Feed Discovery
        if self.enable_feeds:
            feed_parser = FeedParser(self.domain_clean, allow_external=self.allow_external)
            candidate_feeds = [
                f"https://{self.domain_clean}/feed",
                f"https://{self.domain_clean}/feed.xml",
                f"https://{self.domain_clean}/rss.xml",
                f"https://{self.domain_clean}/atom.xml",
            ]
            for item in html_results:
                for link in item.get("discovered_links", []):
                    link_lower = link.lower()
                    if any(link_lower.endswith(ext) for ext in [".xml", ".rss", ".atom", "/feed", "/feed/"]):
                        if link not in candidate_feeds:
                            candidate_feeds.append(link)

            for feed_url in candidate_feeds[:8]:
                try:
                    feed_items = await feed_parser.parse_feed(feed_url)
                    for f_item in feed_items:
                        norm = f_item["normalized_url"]
                        h = compute_url_hash(norm)
                        if h not in discovered_map:
                            discovered_map[h] = {
                                "original_url": f_item["original_url"],
                                "normalized_url": norm,
                                "url_hash": h,
                                "source": "feed",
                                "http_status": 200,
                                "content_hash": None,
                                "is_redirect": False,
                                "resolved_url": norm,
                            }
                            source_counts["feed"] += 1
                except Exception as fe:
                    logger.debug(f"Feed parse error on {feed_url}: {fe}")

        # 5. Database Persistence & Deduplication
        new_count = 0
        existing_count = 0
        changed_content_count = 0
        now = utc_now()

        # Batch query existing URLs in chunks of 500 to optimize for thousands of URLs
        all_hashes = list(discovered_map.keys())
        existing_map: dict[str, Url] = {}
        for i in range(0, len(all_hashes), 500):
            chunk = all_hashes[i:i + 500]
            for u in db.query(Url).filter(Url.url_hash.in_(chunk)).all():
                existing_map[u.url_hash] = u

        for h, item in discovered_map.items():
            existing = existing_map.get(h)
            if existing:
                existing.last_seen = now
                if item.get("http_status"):
                    existing.http_status = item["http_status"]
                if item.get("content_hash"):
                    if existing.content_hash and item["content_hash"] != existing.content_hash:
                        existing.previous_content_hash = existing.content_hash
                        existing.content_changed = True
                        changed_content_count += 1
                    existing.content_hash = item["content_hash"]
                if item.get("is_redirect"):
                    existing.is_redirect = item["is_redirect"]
                    existing.resolved_url = item.get("resolved_url")
                existing_count += 1
            else:
                new_url = Url(
                    domain_id=domain_id,
                    original_url=item["original_url"],
                    normalized_url=item["normalized_url"],
                    url_hash=h,
                    discovery_source=item.get("source", "html"),
                    discovery_timestamp=now,
                    last_seen=now,
                    http_status=item.get("http_status"),
                    content_hash=item.get("content_hash"),
                    previous_content_hash=None,
                    content_changed=False,
                    is_redirect=item.get("is_redirect", False),
                    resolved_url=item.get("resolved_url"),
                )
                db.add(new_url)
                new_count += 1

        domain_record.last_scan_at = now
        db.commit()

        total_urls = db.query(Url).filter(Url.domain_id == domain_id).count()
        crawl_duration = round(time.time() - start_time, 2)
        total_discovered = len(discovered_map)
        crawl_speed = round(total_discovered / crawl_duration, 1) if crawl_duration > 0 else float(total_discovered)

        return {
            "domain_id": domain_id,
            "domain": self.domain_clean,
            "new_urls_discovered": new_count,
            "existing_urls_refreshed": existing_count,
            "content_changes_detected": changed_content_count,
            "total_urls_in_domain": total_urls,
            "source_breakdown": source_counts,
            "sitemaps_inspected": len(sitemap_urls),
            "scan_timestamp": now.isoformat(),
            "crawl_duration_seconds": crawl_duration,
            "crawl_speed_urls_per_sec": crawl_speed,
        }
