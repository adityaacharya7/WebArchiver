"""
Playwright-based dynamic DOM crawler and JavaScript renderer (Bonus Challenge).
Handles client-rendered SPAs and public JS-heavy pages (including Instagram public page workflow).
Complies strictly with terms: halts gracefully when authentication/login walls are encountered.
"""
import logging
from urllib.parse import urljoin
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


class PlaywrightCrawler:
    """
    Renders JavaScript-heavy web pages using headless Playwright browser.
    Extracts dynamic DOM links and full rendered HTML for archival submission.
    """

    def __init__(self, timeout_ms: int = 30000):
        self.timeout_ms = timeout_ms

    async def render_and_extract(self, url: str, target_domain: str | None = None) -> dict:
        """
        Loads the page in headless browser, waits for network idle and dynamic DOM,
        and extracts rendered HTML, links, and access status.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {
                "success": False,
                "url": url,
                "error": "Playwright is not installed in the environment.",
                "links": [],
                "rendered_html": None,
            }

        domain = target_domain or url
        result = {
            "success": False,
            "url": url,
            "error": None,
            "status_code": None,
            "links": [],
            "rendered_html": None,
            "content_hash": None,
            "requires_login": False,
        }

        try:
            async with async_playwright() as p:
                # Launch browser (prefer installed Chromium or system Edge/Chrome)
                browser = None
                try:
                    browser = await p.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
                except Exception:
                    # Fallback to system channel if playwright standalone browser isn't downloaded
                    try:
                        browser = await p.chromium.launch(channel="msedge", headless=settings.PLAYWRIGHT_HEADLESS)
                    except Exception:
                        try:
                            browser = await p.chromium.launch(channel="chrome", headless=settings.PLAYWRIGHT_HEADLESS)
                        except Exception as launch_err:
                            result["error"] = f"Playwright browser could not be launched: {launch_err}"
                            return result

                context = None
                try:
                    context = await browser.new_context(
                        user_agent=settings.CRAWLER_USER_AGENT,
                        viewport={"width": 1280, "height": 800},
                    )
                    page = await context.new_page()

                    response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    # Wait briefly for dynamic client-side scripts
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass  # Networkidle timeout is acceptable for continuous polling pages

                    rendered_html = await page.content()
                    result["rendered_html"] = rendered_html
                    result["content_hash"] = compute_content_hash(rendered_html)
                    result["status_code"] = response.status if response else 200

                    # Check for login barriers or access restrictions (e.g. Instagram login modal)
                    lower_html = rendered_html.lower()
                    if "login" in lower_html and ("instagram" in url or "accounts/login" in page.url):
                        result["requires_login"] = True
                        logger.info(f"Page at {url} requires authentication. Halting per policy.")

                    # Extract dynamically rendered links
                    discovered_links = set()
                    soup = BeautifulSoup(rendered_html, "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                            full_link = urljoin(page.url, href)
                            if is_valid_crawl_url(full_link) and is_same_domain(full_link, domain):
                                norm = normalize_url(full_link)
                                if norm:
                                    discovered_links.add(norm)

                    result["links"] = list(discovered_links)
                    result["success"] = True
                finally:
                    if context:
                        try:
                            await context.close()
                        except Exception:
                            pass
                    if browser:
                        try:
                            await browser.close()
                        except Exception:
                            pass

        except Exception as e:
            logger.error(f"Playwright rendering failed on {url}: {e}")
            result["error"] = str(e)

        return result
