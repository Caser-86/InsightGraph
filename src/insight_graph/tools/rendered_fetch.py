from __future__ import annotations

from urllib.parse import urlparse

from insight_graph.tools.http_client import FetchedPage, FetchError


def render_page(url: str, timeout: float = 10.0) -> FetchedPage:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise FetchError(f"Unsupported URL scheme: {parsed.scheme or 'missing'}")
    if not parsed.netloc:
        raise FetchError("URL host is required")

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise FetchError("Rendered fetch requires optional Playwright dependency") from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                response = page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=int(timeout * 1000),
                )
                html = page.content()
                status_code = response.status if response is not None else 200
                if status_code < 200 or status_code >= 300:
                    raise FetchError(f"Unexpected HTTP status: {status_code}")
                content_type = (
                    response.headers.get("content-type", "text/html")
                    if response is not None
                    else "text/html"
                )
                return FetchedPage(
                    url=page.url,
                    status_code=status_code,
                    content_type=content_type,
                    text=html,
                    body=html.encode("utf-8"),
                )
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise FetchError(f"Rendered fetch failed: {exc}") from exc
