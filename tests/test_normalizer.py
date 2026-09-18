"""
Unit tests for URL normalizer, deduplication hashing, and domain validation.
"""
import pytest
from backend.app.normalizer.normalizer import (
    normalize_url,
    compute_url_hash,
    compute_content_hash,
    is_valid_crawl_url,
    is_same_domain,
    clean_domain_name,
)


def test_normalize_url_basic():
    # Scheme and host lowercasing
    assert normalize_url("HTTP://Example.COM/Path") == "http://example.com/Path"
    # Root path preservation
    assert normalize_url("https://example.com") == "https://example.com/"
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_normalize_url_ports():
    # Strip standard ports
    assert normalize_url("http://example.com:80/page") == "http://example.com/page"
    assert normalize_url("https://example.com:443/page") == "https://example.com/page"
    # Retain non-standard ports
    assert normalize_url("http://example.com:8080/page") == "http://example.com:8080/page"


def test_normalize_url_tracking_params():
    # Strip tracking parameters and utm_* tags
    url = "https://example.com/article?utm_source=twitter&utm_medium=social&utm_campaign=spring&id=123&fbclid=xyz"
    expected = "https://example.com/article?id=123"
    assert normalize_url(url) == expected


def test_normalize_url_query_sorting():
    # Sort query parameters alphabetically
    url1 = "https://example.com/search?z=last&a=first&m=middle"
    url2 = "https://example.com/search?a=first&m=middle&z=last"
    assert normalize_url(url1) == "https://example.com/search?a=first&m=middle&z=last"
    assert normalize_url(url1) == normalize_url(url2)
    # Hashing matching query parameters should be identical
    assert compute_url_hash(normalize_url(url1)) == compute_url_hash(normalize_url(url2))


def test_normalize_url_fragments():
    # Fragments must be stripped from normalized URL
    url_with_fragment = "https://example.com/doc#section-2"
    url_without_fragment = "https://example.com/doc"
    assert normalize_url(url_with_fragment) == "https://example.com/doc"
    assert compute_url_hash(normalize_url(url_with_fragment)) == compute_url_hash(normalize_url(url_without_fragment))


def test_normalize_url_path_segments():
    # Collapse multiple slashes and resolve relative segments
    assert normalize_url("https://example.com/a//b///c") == "https://example.com/a/b/c"
    assert normalize_url("https://example.com/a/b/../c") == "https://example.com/a/c"


def test_normalize_url_trailing_slashes():
    # Non-root paths standardized
    assert normalize_url("https://example.com/about/") == "https://example.com/about"
    assert normalize_url("https://example.com/about") == "https://example.com/about"
    assert compute_url_hash(normalize_url("https://example.com/about/")) == compute_url_hash(normalize_url("https://example.com/about"))


def test_relative_url_resolution():
    base = "https://example.com/blog/article1"
    assert normalize_url("/contact", base_url=base) == "https://example.com/contact"
    assert normalize_url("article2", base_url=base) == "https://example.com/blog/article2"


def test_is_valid_crawl_url():
    assert is_valid_crawl_url("https://example.com/page.html") is True
    assert is_valid_crawl_url("http://example.com/") is True
    assert is_valid_crawl_url("javascript:void(0)") is False
    assert is_valid_crawl_url("mailto:info@example.com") is False
    assert is_valid_crawl_url("tel:+123456789") is False
    assert is_valid_crawl_url("https://example.com/installer.exe") is False
    assert is_valid_crawl_url("https://example.com/archive.zip") is False


def test_is_same_domain():
    target = "example.com"
    assert is_same_domain("https://example.com/path", target) is True
    assert is_same_domain("https://www.example.com/path", target) is True
    assert is_same_domain("https://blog.example.com/path", target, allow_subdomains=True) is True
    assert is_same_domain("https://otherdomain.com/path", target) is False
    assert is_same_domain("https://notexample.com/path", target) is False
    # Embedded www in domain name should not be corrupted
    assert is_same_domain("https://news-www.org/item", "news-www.org") is True
    assert is_same_domain("https://other.com/item", "news-www.org") is False


def test_clean_domain_name():
    assert clean_domain_name("https://www.example.com/path/to/page") == "www.example.com"
    assert clean_domain_name("example.com") == "example.com"
    assert clean_domain_name("http://Sub.Domain.org:8080/") == "sub.domain.org"


def test_compute_hashes():
    h1 = compute_url_hash("https://example.com/")
    assert len(h1) == 64
    c1 = compute_content_hash("<html><body>Test</body></html>")
    c2 = compute_content_hash("<html><body>Test</body></html>")
    assert c1 == c2
    assert len(c1) == 64


def test_normalizer_malformed_inputs():
    """Verify that malformed URLs and bracketed hosts do not crash urlparse."""
    assert clean_domain_name("http://[invalid-ipv6]") == ""
    assert clean_domain_name(":::invalid:::") == ""
    assert clean_domain_name(None) == ""
    assert normalize_url("http://[invalid-ipv6]/path") == ""
    assert normalize_url("http://:80/path") == ""
    assert normalize_url(None) == ""
    assert is_valid_crawl_url("http://[invalid-ipv6]") is False
    assert is_valid_crawl_url(None) is False
    assert is_same_domain("http://[invalid-ipv6]", "example.com") is False
    assert is_same_domain(None, "example.com") is False
