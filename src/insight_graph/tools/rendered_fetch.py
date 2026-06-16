from __future__ import annotations

from urllib.parse import urlparse

from insight_graph.tools.http_client import FetchedPage, FetchError, validate_fetch_url


def render_page(url: str, timeout: float = 10.0) -> FetchedPage:
    validate_fetch_url(url)
    blocked_error: FetchError | None = None
    validated_origins: set[str] = set()

    def _set_blocked_error(error: FetchError) -> None:
        nonlocal blocked_error
        if blocked_error is None:
            blocked_error = error

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
                page.route(
                    "**/*",
                    lambda route: _guard_browser_route(
                        route,
                        validated_origins,
                        lambda error: _set_blocked_error(error),
                    ),
                )
                response = page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=int(timeout * 1000),
                )
                if blocked_error is not None:
                    raise blocked_error
                validate_fetch_url(page.url)
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
        if blocked_error is not None:
            raise blocked_error from exc
        raise FetchError(f"Rendered fetch failed: {exc}") from exc


def _guard_browser_route(route, validated_origins: set[str], set_error) -> None:
    request_url = route.request.url
    parsed = urlparse(request_url)
    origin = f"{parsed.scheme}://{parsed.netloc}".lower()
    if origin in validated_origins:
        route.continue_()
        return

    try:
        validate_fetch_url(request_url)
    except FetchError as exc:
        set_error(exc)
        route.abort("blockedbyclient")
        return

    validated_origins.add(origin)
    route.continue_()
