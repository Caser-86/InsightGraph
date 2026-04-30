from __future__ import annotations

import ipaddress
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel

DEFAULT_MAX_RESPONSE_BYTES = 2_000_000
READ_CHUNK_BYTES = 64 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/xhtml+xml",
    "text/html",
    "text/markdown",
    "text/plain",
    "text/xml",
}


class FetchError(RuntimeError):
    pass


class FetchedPage(BaseModel):
    url: str
    status_code: int
    content_type: str
    text: str
    body: bytes | None = None


def fetch_text(
    url: str,
    timeout: float = 10.0,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> FetchedPage:
    parsed = urlparse(url)
    _validate_url(parsed)

    request = Request(url, headers={"User-Agent": "InsightGraph/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            final_url = _response_url(response, url)
            _validate_url(urlparse(final_url))
            status_code = getattr(response, "status", 200)
            if status_code < 200 or status_code >= 300:
                raise FetchError(f"Unexpected HTTP status: {status_code}")
            content_type = response.headers.get("Content-Type", "")
            _validate_content_type(content_type)
            content_length = _content_length_from_headers(response.headers)
            if content_length is not None and content_length > max_bytes:
                raise FetchError(f"Response body too large: {content_length} bytes")
            body = _read_bounded_body(response, max_bytes)
            if not body:
                raise FetchError("Empty response body")
            encoding = _encoding_from_content_type(content_type)
            text = _decode_body(body, encoding)
            return FetchedPage(
                url=final_url,
                status_code=status_code,
                content_type=content_type,
                text=text,
                body=body,
            )
    except HTTPError as exc:
        raise FetchError(f"HTTP error while fetching URL: {exc.code}") from exc
    except URLError as exc:
        raise FetchError(f"Network error while fetching URL: {exc.reason}") from exc


def _validate_url(parsed: ParseResult) -> None:
    if parsed.scheme not in {"http", "https"}:
        raise FetchError(f"Unsupported URL scheme: {parsed.scheme or 'missing'}")
    if not parsed.netloc or not parsed.hostname:
        raise FetchError("URL host is required")
    if _host_is_blocked(parsed.hostname, parsed.port):
        raise FetchError("URL host is not allowed")


def _host_is_blocked(host: str, port: int | None) -> bool:
    if host.lower().rstrip(".") == "localhost":
        return True
    if _is_blocked_ip(host):
        return True
    for ip in _resolve_host_ips(host, port):
        if _is_blocked_ip(ip):
            return True
    return False


def _resolve_host_ips(host: str, port: int | None) -> list[str]:
    try:
        return [info[4][0] for info in socket.getaddrinfo(host, port or 443)]
    except socket.gaierror as exc:
        raise FetchError(f"Unable to resolve URL host: {host}") from exc


def _is_blocked_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _response_url(response, fallback_url: str) -> str:
    geturl = getattr(response, "geturl", None)
    if geturl is None:
        return fallback_url
    final_url = geturl()
    return final_url if isinstance(final_url, str) and final_url else fallback_url


def _validate_content_type(content_type: str) -> None:
    media_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    if not media_type:
        return
    if media_type in ALLOWED_CONTENT_TYPES or media_type.endswith("+xml"):
        return
    raise FetchError(f"Unsupported content type: {media_type}")


def _read_bounded_body(response, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FetchError(f"Response body too large: {total} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _encoding_from_content_type(content_type: str) -> str:
    for part in content_type.split(";"):
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value:
            return value
    return "utf-8"


def _content_length_from_headers(headers) -> int | None:
    value = headers.get("Content-Length", "")
    try:
        content_length = int(value)
    except (TypeError, ValueError):
        return None
    return content_length if content_length >= 0 else None


def _decode_body(body: bytes, encoding: str) -> str:
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")
