from urllib.error import HTTPError, URLError

import pytest

from insight_graph.tools.http_client import FetchError, fetch_text


@pytest.fixture(autouse=True)
def _avoid_live_dns(monkeypatch):
    monkeypatch.setattr(
        "insight_graph.tools.http_client._resolve_host_ips",
        lambda host, port: ["93.184.216.34"],
        raising=False,
    )


class FakeResponse:
    status = 200

    def __init__(
        self,
        body: bytes,
        content_type: str = "text/html; charset=utf-8",
        *,
        chunk_size: int | None = None,
    ) -> None:
        self._body = body
        self.headers = {"Content-Type": content_type}
        self._chunk_size = chunk_size
        self._offset = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, size: int | None = None) -> bytes:
        if self._chunk_size is None and size is None:
            return self._body
        chunk_size = self._chunk_size if self._chunk_size is not None else size
        if chunk_size is None:
            return self._body
        chunk = self._body[self._offset : self._offset + chunk_size]
        self._offset += len(chunk)
        return chunk


def test_fetch_text_rejects_unsupported_scheme() -> None:
    with pytest.raises(FetchError, match="Unsupported URL scheme"):
        fetch_text("ftp://example.com/file")


def test_fetch_text_rejects_missing_host() -> None:
    with pytest.raises(FetchError, match="URL host is required"):
        fetch_text("https:///path")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/internal",
        "http://172.16.0.1/internal",
        "http://192.168.1.1/internal",
        "http://[::1]/internal",
    ],
)
def test_fetch_text_rejects_private_or_local_hosts(url) -> None:
    with pytest.raises(FetchError, match="URL host is not allowed") as exc_info:
        fetch_text(url)
    assert exc_info.value.kind == "blocked_url"


def test_fetch_text_tags_blocked_url_errors() -> None:
    with pytest.raises(FetchError, match="URL host is not allowed") as exc_info:
        fetch_text("http://127.0.0.1/admin")

    assert exc_info.value.kind == "blocked_url"


def test_fetch_text_rejects_hostname_that_resolves_to_private_ip(monkeypatch) -> None:
    def fail_if_called(request, timeout):
        raise AssertionError("network request should not run")

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fail_if_called)
    monkeypatch.setattr(
        "insight_graph.tools.http_client._resolve_host_ips",
        lambda host, port: ["127.0.0.1"],
        raising=False,
    )

    with pytest.raises(FetchError, match="URL host is not allowed"):
        fetch_text("https://example.com/private")


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
        return FakeResponse(b"abcdef", chunk_size=2)

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    with pytest.raises(FetchError, match="Response body too large: 6 bytes"):
        fetch_text("https://example.com/large", max_bytes=5)


def test_fetch_text_rejects_content_length_over_max_bytes_before_reading(
    monkeypatch,
) -> None:
    class NoReadResponse(FakeResponse):
        def __init__(self) -> None:
            super().__init__(b"abcdef")
            self.headers["Content-Length"] = "6"
            self.read_called = False

        def read(self, size: int | None = None) -> bytes:
            self.read_called = True
            raise AssertionError("body should not be read")

    response = NoReadResponse()

    def fake_urlopen(request, timeout):
        return response

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    with pytest.raises(FetchError, match="Response body too large: 6 bytes"):
        fetch_text("https://example.com/large", max_bytes=5)
    assert response.read_called is False


def test_fetch_text_rejects_non_success_status(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        response = FakeResponse(b"error")
        response.status = 500
        return response

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    with pytest.raises(FetchError, match="Unexpected HTTP status: 500"):
        fetch_text("https://example.com/server-error")


def test_fetch_text_rejects_disallowed_content_type(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeResponse(b"binary", "application/octet-stream")

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    with pytest.raises(FetchError, match="Unsupported content type"):
        fetch_text("https://example.com/archive.bin")


def test_fetch_text_revalidates_redirect_target(monkeypatch) -> None:
    class RedirectResponse(FakeResponse):
        def geturl(self) -> str:
            return "http://127.0.0.1/admin"

    def fake_urlopen(request, timeout):
        return RedirectResponse(b"secret")

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    with pytest.raises(FetchError, match="URL host is not allowed"):
        fetch_text("https://example.com/redirect")


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


def test_fetch_text_retries_transient_network_error(monkeypatch) -> None:
    attempts = []
    sleeps = []

    def fake_urlopen(request, timeout):
        attempts.append(request.full_url)
        if len(attempts) == 1:
            raise URLError("temporary failure")
        return FakeResponse(b"ok")

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    page = fetch_text(
        "https://example.com/retry",
        retries=1,
        backoff_seconds=0.25,
        sleep_func=sleeps.append,
    )

    assert page.text == "ok"
    assert attempts == ["https://example.com/retry", "https://example.com/retry"]
    assert sleeps == [0.25]


def test_fetch_text_does_not_retry_blocked_url(monkeypatch) -> None:
    def fail_if_called(request, timeout):
        raise AssertionError("network request should not run")

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fail_if_called)

    with pytest.raises(FetchError, match="URL host is not allowed") as exc_info:
        fetch_text("http://127.0.0.1/admin", retries=3)

    assert exc_info.value.kind == "blocked_url"


def test_fetch_text_falls_back_for_unknown_charset(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeResponse("Café".encode(), "text/html; charset=not-a-codec")

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    page = fetch_text("https://example.com/unknown-charset")

    assert page.text == "Café"
