"""Normalizer package."""
from backend.app.normalizer.normalizer import (
    normalize_url,
    compute_url_hash,
    compute_content_hash,
    is_valid_crawl_url,
    is_same_domain,
    clean_domain_name,
)

__all__ = [
    "normalize_url",
    "compute_url_hash",
    "compute_content_hash",
    "is_valid_crawl_url",
    "is_same_domain",
    "clean_domain_name",
]
