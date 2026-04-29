from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel


class FetchError(RuntimeError):
    pass


class FetchedPage(BaseModel):
    url: str
    status_code: int
    content_type: str
    text: str
    body: bytes | None = None


def fetch_text(url: str, timeout: float = 10.0) -> FetchedPage:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise FetchError(f"Unsupported URL scheme: {parsed.scheme or 'missing'}")
    if not parsed.netloc:
        raise FetchError("URL host is required")

    request = Request(url, headers={"User-Agent": "InsightGraph/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            if status_code < 200 or status_code >= 300:
                raise FetchError(f"Unexpected HTTP status: {status_code}")
            body = response.read()
            if not body:
                raise FetchError("Empty response body")
            content_type = response.headers.get("Content-Type", "")
            encoding = _encoding_from_content_type(content_type)
            text = _decode_body(body, encoding)
            return FetchedPage(
                url=url,
                status_code=status_code,
                content_type=content_type,
                text=text,
                body=body,
            )
    except HTTPError as exc:
        raise FetchError(f"HTTP error while fetching URL: {exc.code}") from exc
    except URLError as exc:
        raise FetchError(f"Network error while fetching URL: {exc.reason}") from exc


def _encoding_from_content_type(content_type: str) -> str:
    for part in content_type.split(";"):
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value:
            return value
    return "utf-8"


def _decode_body(body: bytes, encoding: str) -> str:
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")
