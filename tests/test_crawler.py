"""
Unit tests for crawler components: robots, sitemaps, feeds, HTML crawler, and discovery manager.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import Base
from backend.app.db.models import Domain, Url
from backend.app.crawler.robots import RobotsParser
from backend.app.crawler.sitemap import SitemapParser
from backend.app.crawler.feeds import FeedParser
from backend.app.crawler.html_crawler import HtmlCrawler
from backend.app.crawler.discovery_manager import DiscoveryManager


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.mark.anyio
async def test_robots_parser():
    robots_txt = """
    User-agent: *
    Disallow: /admin
    Disallow: /private/
    Sitemap: https://example.com/custom-sitemap.xml
    Sitemap: /relative-sitemap.xml
    Sitemap: https://example.com/sitemap2.xml
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = robots_txt

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        parser = RobotsParser("example.com")
        res = await parser.fetch_and_parse()

        assert "https://example.com/custom-sitemap.xml" in res["sitemaps"]
        assert "https://example.com/relative-sitemap.xml" in res["sitemaps"]
        assert "https://example.com/sitemap2.xml" in res["sitemaps"]
        assert "https://example.com/sitemap.xml" in res["sitemaps"]  # fallback included
        assert "/admin" in res["disallowed_paths"]


@pytest.mark.anyio
async def test_sitemap_parser():
    sitemap_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://example.com/page1</loc>
        </url>
        <url>
            <loc>https://example.com/page2</loc>
        </url>
        <url>
            <loc>https://otherdomain.com/unrelated</loc>
        </url>
    </urlset>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = sitemap_xml

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        parser = SitemapParser("example.com")
        urls = await parser.parse_sitemap("https://example.com/sitemap.xml")

        assert len(urls) == 2
        normalized_urls = [u["normalized_url"] for u in urls]
        assert "https://example.com/page1" in normalized_urls
        assert "https://example.com/page2" in normalized_urls
        assert "https://otherdomain.com/unrelated" not in normalized_urls


@pytest.mark.anyio
async def test_sitemap_parser_gzip():
    import gzip
    sitemap_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/gz-page1</loc></url>
        <url><loc>https://example.com/gz-page2</loc></url>
    </urlset>
    """
    gzipped_content = gzip.compress(sitemap_xml)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = gzipped_content

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        parser = SitemapParser("example.com")
        urls = await parser.parse_sitemap("https://example.com/sitemap.xml.gz")

        assert len(urls) == 2
        normalized_urls = [u["normalized_url"] for u in urls]
        assert "https://example.com/gz-page1" in normalized_urls
        assert "https://example.com/gz-page2" in normalized_urls


@pytest.mark.anyio
async def test_feed_parser():
    html = """
    <html>
        <head>
            <link rel="alternate" type="application/rss+xml" title="RSS" href="/feed.xml" />
        </head>
        <body>Test</body>
    </html>
    """
    parser = FeedParser("example.com")
    links = parser.extract_feed_links(html, "https://example.com")
    assert links == ["https://example.com/feed.xml"]

    rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <item><link>https://example.com/blog/post-1</link></item>
            <item><link>https://example.com/blog/post-2</link></item>
        </channel>
    </rss>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = rss_xml

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        discovered = await parser.parse_feed("https://example.com/feed.xml")
        assert len(discovered) == 2
        assert discovered[0]["normalized_url"] == "https://example.com/blog/post-1"


@pytest.mark.anyio
async def test_html_crawler_link_extraction():
    html_page1 = """
    <html>
        <head><link rel="canonical" href="https://example.com/home" /></head>
        <body>
            <a href="/about">About Us</a>
            <a href="/contact/">Contact</a>
            <a href="https://external.com/out">External</a>
        </body>
    </html>
    """
    crawler = HtmlCrawler("example.com")
    extracted = crawler._extract_links(html_page1, "https://example.com")
    assert "https://example.com/about" in extracted
    assert "https://example.com/contact/" in extracted
    assert "https://example.com/home" in extracted


@pytest.mark.anyio
async def test_discovery_manager_integration(test_db):
    html_home = """
    <html>
        <body>
            <a href="/page-a">Page A</a>
            <a href="/page-b">Page B</a>
        </body>
    </html>
    """
    mock_resp_robots = MagicMock(status_code=404, text="")
    mock_resp_sitemap = MagicMock(status_code=404, content=b"")
    mock_resp_home = MagicMock(status_code=200, text=html_home, headers={"content-type": "text/html"}, url="https://mysite.org/")
    mock_resp_page_a = MagicMock(status_code=200, text="<html><body>A</body></html>", headers={"content-type": "text/html"}, url="https://mysite.org/page-a")
    mock_resp_page_b = MagicMock(status_code=200, text="<html><body>B</body></html>", headers={"content-type": "text/html"}, url="https://mysite.org/page-b")

    async def mock_get(url, *args, **kwargs):
        url_str = str(url)
        if "robots.txt" in url_str:
            return mock_resp_robots
        elif "sitemap.xml" in url_str:
            return mock_resp_sitemap
        elif "page-a" in url_str:
            return mock_resp_page_a
        elif "page-b" in url_str:
            return mock_resp_page_b
        return mock_resp_home

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        manager = DiscoveryManager("mysite.org", max_depth=2, max_pages=10)
        report = await manager.run_discovery(test_db)

        assert report["domain"] == "mysite.org"
        assert report["new_urls_discovered"] >= 3  # home, page-a, page-b

        # Verify URLs in test_db
        db_urls = test_db.query(Url).all()
        assert len(db_urls) >= 3

        # Test deduplication on second run
        report2 = await manager.run_discovery(test_db)
        assert report2["new_urls_discovered"] == 0
        assert report2["existing_urls_refreshed"] >= 3


@pytest.mark.anyio
async def test_discovery_manager_invalid_domain(test_db):
    manager = DiscoveryManager(":::invalid-domain:::")
    with pytest.raises(ValueError, match="Invalid domain name"):
        await manager.run_discovery(test_db)

