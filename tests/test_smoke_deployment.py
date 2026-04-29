import io
import json
from pathlib import Path

import insight_graph.smoke as smoke_module


def test_pyproject_registers_smoke_console_script() -> None:
    pyproject = Path(__file__).parents[1] / "pyproject.toml"

    assert 'insight-graph-smoke = "insight_graph.smoke:main"' in pyproject.read_text(
        encoding="utf-8"
    )


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


def test_run_smoke_records_created_at_and_durations() -> None:
    clock_values = iter([1000.0, 1000.0, 1000.1, 1000.1, 1000.3, 1000.3, 1000.6, 1001.0])

    def fake_now() -> str:
        return "2026-04-29T04:00:00Z"

    def fake_monotonic() -> float:
        return next(clock_values)

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        if url.endswith("/dashboard"):
            return FakeResponse(status_code=200, body="InsightGraph", content_type="text/html")
        return FakeResponse(status_code=200, body="{}", content_type="application/json")

    result = smoke_module.run_smoke(
        "https://insightgraph.example.com",
        http_get=fake_get,
        now=fake_now,
        monotonic=fake_monotonic,
    )

    assert result["created_at"] == "2026-04-29T04:00:00Z"
    assert result["duration_ms"] == 1000
    assert [check["duration_ms"] for check in result["checks"]] == [100, 200, 300]


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


def test_main_can_print_markdown_summary() -> None:
    def fake_get(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        if url.endswith("/dashboard"):
            return FakeResponse(status_code=200, body="InsightGraph", content_type="text/html")
        return FakeResponse(status_code=200, body="{}", content_type="application/json")

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = smoke_module.main(
        ["https://insightgraph.example.com", "--markdown"],
        stdout=stdout,
        stderr=stderr,
        http_get=fake_get,
    )

    markdown = stdout.getvalue()
    assert exit_code == 0
    assert "# Deployment Smoke Test" in markdown
    assert "Base URL: `https://insightgraph.example.com`" in markdown
    assert "Created at:" in markdown
    assert "Duration ms:" in markdown
    assert "| Check | Status | HTTP | Duration ms | Error |" in markdown
    assert "| health | PASS | 200 |" in markdown
    assert "| dashboard | PASS | 200 |" in markdown
    assert "| jobs_summary | PASS | 200 |" in markdown
    assert stderr.getvalue() == ""


def test_markdown_summary_includes_failure_error_details() -> None:
    markdown = smoke_module.format_markdown(
        {
            "ok": False,
            "base_url": "https://insightgraph.example.com",
            "created_at": "2026-04-29T04:00:00Z",
            "duration_ms": 42,
            "checks": [
                {
                    "name": "health",
                    "ok": False,
                    "status_code": 503,
                    "duration_ms": 10,
                    "error": "bad | status\ntry proxy logs",
                }
            ],
        }
    )

    assert "| Check | Status | HTTP | Duration ms | Error |" in markdown
    assert "| health | FAIL | 503 | 10 | bad \\| status try proxy logs |" in markdown


def test_main_can_write_json_output_file(tmp_path) -> None:
    output_path = tmp_path / "smoke.json"

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        if url.endswith("/dashboard"):
            return FakeResponse(status_code=200, body="InsightGraph", content_type="text/html")
        return FakeResponse(status_code=200, body="{}", content_type="application/json")

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = smoke_module.main(
        ["https://insightgraph.example.com", "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
        http_get=fake_get,
    )

    assert exit_code == 0
    assert stdout.getvalue() == ""
    assert json.loads(output_path.read_text(encoding="utf-8"))["ok"] is True
    assert stderr.getvalue() == ""


def test_main_can_write_markdown_output_file(tmp_path) -> None:
    output_path = tmp_path / "smoke.md"

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        if url.endswith("/dashboard"):
            return FakeResponse(status_code=200, body="InsightGraph", content_type="text/html")
        return FakeResponse(status_code=200, body="{}", content_type="application/json")

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = smoke_module.main(
        ["https://insightgraph.example.com", "--markdown", "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
        http_get=fake_get,
    )

    assert exit_code == 0
    assert stdout.getvalue() == ""
    assert "# Deployment Smoke Test" in output_path.read_text(encoding="utf-8")
    assert stderr.getvalue() == ""


def test_main_returns_two_when_output_file_cannot_be_written(tmp_path) -> None:
    output_path = tmp_path / "missing" / "smoke.json"

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        if url.endswith("/dashboard"):
            return FakeResponse(status_code=200, body="InsightGraph", content_type="text/html")
        return FakeResponse(status_code=200, body="{}", content_type="application/json")

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = smoke_module.main(
        ["https://insightgraph.example.com", "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
        http_get=fake_get,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "Failed to write smoke report:" in stderr.getvalue()
