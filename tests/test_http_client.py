from urllib.error import HTTPError, URLError

import pytest

from insight_graph.tools.http_client import FetchError, fetch_text


class FakeResponse:
    status = 200

    def __init__(self, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self._body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_fetch_text_rejects_unsupported_scheme() -> None:
    with pytest.raises(FetchError, match="Unsupported URL scheme"):
        fetch_text("ftp://example.com/file")


def test_fetch_text_rejects_missing_host() -> None:
    with pytest.raises(FetchError, match="URL host is required"):
        fetch_text("https:///path")


def test_fetch_text_decodes_response(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        assert request.full_url == "https://example.com/page"
        assert timeout == 10.0
        return FakeResponse("Café".encode())

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    page = fetch_text("https://example.com/page")

    assert page.url == "https://example.com/page"
    assert page.status_code == 200
    assert page.content_type == "text/html; charset=utf-8"
    assert page.text == "Café"


def test_fetch_text_rejects_empty_body(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeResponse(b"")

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    with pytest.raises(FetchError, match="Empty response body"):
        fetch_text("https://example.com/empty")


def test_fetch_text_rejects_response_over_max_bytes(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeResponse(b"abcdef")

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    with pytest.raises(FetchError, match="Response body too large: 6 bytes"):
        fetch_text("https://example.com/large", max_bytes=5)


def test_fetch_text_rejects_non_success_status(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        response = FakeResponse(b"error")
        response.status = 500
        return response

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    with pytest.raises(FetchError, match="Unexpected HTTP status: 500"):
        fetch_text("https://example.com/server-error")


def test_fetch_text_wraps_http_error(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    with pytest.raises(FetchError, match="HTTP error while fetching URL: 404"):
        fetch_text("https://example.com/missing")


def test_fetch_text_wraps_url_error(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    with pytest.raises(FetchError, match="Network error while fetching URL"):
        fetch_text("https://example.com/unreachable")


def test_fetch_text_falls_back_for_unknown_charset(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeResponse("Café".encode(), "text/html; charset=not-a-codec")

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    page = fetch_text("https://example.com/unknown-charset")

    assert page.text == "Café"
