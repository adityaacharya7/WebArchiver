"""Crawler and Discovery package."""
from backend.app.crawler.robots import RobotsParser
from backend.app.crawler.sitemap import SitemapParser
from backend.app.crawler.feeds import FeedParser
from backend.app.crawler.html_crawler import HtmlCrawler
from backend.app.crawler.playwright_crawler import PlaywrightCrawler
from backend.app.crawler.discovery_manager import DiscoveryManager

__all__ = [
    "RobotsParser",
    "SitemapParser",
    "FeedParser",
    "HtmlCrawler",
    "PlaywrightCrawler",
    "DiscoveryManager",
]
