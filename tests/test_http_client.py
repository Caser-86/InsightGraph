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
