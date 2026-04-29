import io
import json

import scripts.smoke_deployment as smoke_module


class FakeResponse:
    def __init__(self, *, status_code: int, body: str, content_type: str) -> None:
        self.status_code = status_code
        self.body = body
        self.content_type = content_type


def test_run_smoke_checks_health_dashboard_and_summary_with_api_key() -> None:
    calls = []

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        calls.append((url, headers, timeout))
        if url.endswith("/health"):
            return FakeResponse(
                status_code=200,
                body='{"status":"ok"}',
                content_type="application/json",
            )
        if url.endswith("/dashboard"):
            return FakeResponse(
                status_code=200,
                body="<title>InsightGraph</title>",
                content_type="text/html",
            )
        if url.endswith("/research/jobs/summary"):
            return FakeResponse(
                status_code=200,
                body='{"queued":0}',
                content_type="application/json",
            )
        raise AssertionError(f"unexpected URL: {url}")

    result = smoke_module.run_smoke(
        "https://insightgraph.example.com/",
        api_key="secret-key",
        timeout=3.5,
        http_get=fake_get,
    )

    assert result["ok"] is True
    assert [check["name"] for check in result["checks"]] == [
        "health",
        "dashboard",
        "jobs_summary",
    ]
    assert calls == [
        ("https://insightgraph.example.com/health", {}, 3.5),
        ("https://insightgraph.example.com/dashboard", {}, 3.5),
        (
            "https://insightgraph.example.com/research/jobs/summary",
            {"Authorization": "Bearer secret-key"},
            3.5,
        ),
    ]


def test_main_returns_one_when_a_check_fails() -> None:
    def fake_get(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        if url.endswith("/health"):
            return FakeResponse(
                status_code=503,
                body='{"status":"down"}',
                content_type="application/json",
            )
        return FakeResponse(status_code=200, body="{}", content_type="application/json")

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = smoke_module.main(
        ["http://127.0.0.1:8000", "--api-key", "secret-key"],
        stdout=stdout,
        stderr=stderr,
        http_get=fake_get,
    )

    payload = json.loads(stdout.getvalue())
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["checks"][0]["name"] == "health"
    assert payload["checks"][0]["ok"] is False
    assert stderr.getvalue() == ""


def test_main_uses_api_key_from_environment(monkeypatch) -> None:
    calls = []
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "env-secret")

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        calls.append((url, headers, timeout))
        if url.endswith("/dashboard"):
            return FakeResponse(status_code=200, body="InsightGraph", content_type="text/html")
        return FakeResponse(status_code=200, body="{}", content_type="application/json")

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = smoke_module.main(
        ["https://insightgraph.example.com"],
        stdout=stdout,
        stderr=stderr,
        http_get=fake_get,
    )

    assert exit_code == 0
    assert calls[2] == (
        "https://insightgraph.example.com/research/jobs/summary",
        {"Authorization": "Bearer env-secret"},
        5.0,
    )
    assert stderr.getvalue() == ""
