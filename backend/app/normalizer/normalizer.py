"""
URL Normalizer, Deduplicator, and Canonical Hash Generator.
Complies with RFC 3986 and assignment Section 6 specifications.
"""
import hashlib
import posixpath
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, urljoin, quote, unquote

# Tracking and analytics parameters to strip
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "msclkid",
    "mc_eid",
    "_ga",
    "_gl",
    "ref",
    "referrer",
    "source",
    "trk",
    "sessionid",
    "phpsessid",
    "jsessionid",
}

# Ignored non-crawlable schemes
IGNORED_SCHEMES = {
    "mailto",
    "tel",
    "sms",
    "javascript",
    "data",
    "file",
    "ftp",
    "blob",
    "irc",
    "magnet",
}

# Common binary file extensions to optionally skip during discovery crawl
BINARY_EXTENSIONS = {
    ".zip", ".tar", ".gz", ".tgz", ".rar", ".7z",
    ".exe", ".msi", ".bin", ".dmg", ".iso",
    ".mp3", ".mp4", ".avi", ".mkv", ".mov", ".wav",
    ".iso", ".apk",
}


def clean_domain_name(domain_str: str) -> str:
    """
    Extract clean domain name (e.g., 'https://www.example.com/path' -> 'example.com').
    """
    if not domain_str or not isinstance(domain_str, str):
        return ""
    
    cleaned = domain_str.strip()
    if not cleaned:
        return ""

    if not cleaned.startswith(("http://", "https://")):
        cleaned = "http://" + cleaned
    
    try:
        parsed = urlparse(cleaned)
        hostname = parsed.hostname or ""
        return hostname.lower().strip()
    except Exception:
        return ""


def compute_url_hash(url_str: str) -> str:
    """Compute SHA-256 hash of a normalized URL string."""
    return hashlib.sha256(url_str.strip().encode("utf-8")).hexdigest()


def compute_content_hash(content: bytes | str) -> str:
    """Compute SHA-256 hash of page content for change detection."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def normalize_url(url: str, base_url: str | None = None) -> str:
    """
    Canonicalize and normalize a URL.
    - Resolves relative URLs if base_url is provided
    - Lowercases scheme and host
    - Strips default ports (80 for http, 443 for https)
    - Resolves '/./' and '/../' in paths
    - Strips fragments (#)
    - Strips common tracking parameters
    - Sorts query parameters
    - Standardizes trailing slash (keeps root '/', strips trailing '/' on sub-paths)
    """
    if not url or not isinstance(url, str):
        return ""

    url = url.strip()
    if not url:
        return ""

    try:
        # Resolve relative URL against base if needed
        if base_url:
            url = urljoin(base_url, url)

        parsed = urlparse(url)

        # Validate scheme
        scheme = (parsed.scheme or "http").lower()
        if scheme not in ("http", "https"):
            return ""

        # Lowercase and clean host
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return ""

        # Port handling (strip default ports)
        port = parsed.port
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            netloc = hostname
        elif port:
            netloc = f"{hostname}:{port}"
        else:
            netloc = hostname

        # Path normalization
        path = parsed.path or "/"
        
        # Normalize path segments (resolve ../ and duplicate //)
        # Ensure leading slash
        if not path.startswith("/"):
            path = "/" + path
        
        # Collapse multiple slashes
        path = re.sub(r"/+", "/", path)
        
        # Standardize posix path
        normalized_path = posixpath.normpath(path)
        if not normalized_path.startswith("/"):
            normalized_path = "/" + normalized_path

        # Preserve or standardize trailing slash:
        # If original was root '/', keep '/'
        # If subpath ended with slash and not a filename with extension, standardize by stripping trailing slash
        if normalized_path != "/":
            if normalized_path.endswith("/"):
                normalized_path = normalized_path.rstrip("/")
        else:
            normalized_path = "/"

        # RFC 3986 Percent-encoding canonicalization
        try:
            normalized_path = quote(unquote(normalized_path), safe="/:@&+$,;~=-_.")
        except Exception:
            pass

        # Query normalization: remove tracking params & sort
        clean_query = ""
        if parsed.query:
            query_params = parse_qsl(parsed.query, keep_blank_values=False)
            filtered_params = [
                (k, v) for k, v in query_params
                if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
            ]
            if filtered_params:
                filtered_params.sort(key=lambda x: (x[0], x[1]))
                clean_query = urlencode(filtered_params)

        # Fragments are stripped per specification (original_url preserves the fragment)
        fragment = ""

        return urlunparse((scheme, netloc, normalized_path, "", clean_query, fragment))
    except Exception:
        return ""


def is_valid_crawl_url(url: str, skip_binary: bool = True) -> bool:
    """Check if URL has a valid HTTP/HTTPS scheme and is suitable for crawling."""
    if not url or not isinstance(url, str):
        return False

    url_lower = url.strip().lower()

    # Reject non-http schemes
    for ignored in IGNORED_SCHEMES:
        if url_lower.startswith(f"{ignored}:"):
            return False

    try:
        parsed = urlparse(url_lower)
        if parsed.scheme not in ("http", "https"):
            return False

        if not parsed.hostname:
            return False

        # Check for binary file extensions
        if skip_binary:
            path = parsed.path.lower()
            if any(path.endswith(ext) for ext in BINARY_EXTENSIONS):
                return False

        return True
    except Exception:
        return False


def is_same_domain(url: str, target_domain: str, allow_subdomains: bool = True) -> bool:
    """
    Check if a URL belongs to the target domain.
    E.g. if target_domain is 'example.com', allows 'example.com' and 'sub.example.com'.
    """
    if not url or not target_domain or not isinstance(url, str) or not isinstance(target_domain, str):
        return False

    try:
        clean_target = clean_domain_name(target_domain)
        if not clean_target:
            return False
        clean_target_no_www = clean_target[4:] if clean_target.startswith("www.") else clean_target

        parsed = urlparse(url)
        url_host = (parsed.hostname or "").lower()

        if not url_host:
            return False

        url_host_no_www = url_host[4:] if url_host.startswith("www.") else url_host

        if url_host_no_www == clean_target_no_www:
            return True

        if allow_subdomains:
            if url_host_no_www.endswith("." + clean_target_no_www):
                return True

        return False
    except Exception:
        return False
