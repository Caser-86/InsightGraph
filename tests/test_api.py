import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import insight_graph.api as api_module
import insight_graph.research_jobs as jobs_module
from insight_graph.cli import LIVE_LLM_PRESET_DEFAULTS
from insight_graph.state import (
    CompetitiveMatrixRow,
    Critique,
    Finding,
    GraphState,
    LLMCallRecord,
    ToolCallRecord,
)


class FakeExecutor:
    def __init__(self) -> None:
        self.submissions: list[tuple[object, tuple[object, ...]]] = []

    def submit(self, func, *args):
        self.submissions.append((func, args))
        return None

    def run_next(self) -> None:
        func, args = self.submissions.pop(0)
        func(*args)


class ImmediateExecutor:
    def submit(self, func, *args):
        func(*args)
        return None


def clear_live_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_PROVIDER",
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_LLM_BASE_URL",
        "INSIGHT_GRAPH_LLM_MODEL",
        "INSIGHT_GRAPH_USE_WEB_SEARCH",
        "INSIGHT_GRAPH_SEARCH_PROVIDER",
        "INSIGHT_GRAPH_RELEVANCE_FILTER",
        "INSIGHT_GRAPH_RELEVANCE_JUDGE",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_api_research_jobs_startup_uses_sqlite_backend_env(monkeypatch, tmp_path) -> None:
    sqlite_path = tmp_path / "jobs.sqlite3"
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", "sqlite")
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", str(sqlite_path))
    monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_PATH", raising=False)

    api_module._initialize_research_jobs_from_env()
    try:
        created = jobs_module.create_research_job(
            query="API env SQLite",
            preset=api_module.ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )
        detail = jobs_module.get_research_job(created["job_id"])
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()

    assert sqlite_path.exists()
    assert detail["status"] == "queued"


def test_api_research_jobs_startup_does_not_reimport_json_over_existing_sqlite(
    monkeypatch,
    tmp_path,
) -> None:
    sqlite_path = tmp_path / "jobs.sqlite3"
    json_path = tmp_path / "jobs.json"
    json_path.write_text(
        """
        {
          "next_job_sequence": 1,
          "jobs": [
            {
              "id": "json-job",
              "query": "JSON",
              "preset": "offline",
              "created_order": 1,
              "created_at": "2026-04-28T10:00:00Z",
              "status": "succeeded",
              "started_at": "2026-04-28T10:00:01Z",
              "finished_at": "2026-04-28T10:00:02Z",
              "result": {"report_markdown": "# JSON"},
              "error": null
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", "sqlite")
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_PATH", str(json_path))

    api_module._initialize_research_jobs_from_env()
    created = jobs_module.create_research_job(
        query="SQLite survivor",
        preset=api_module.ResearchPreset.offline,
        created_at="2026-04-28T10:00:03Z",
    )

    api_module._initialize_research_jobs_from_env()
    try:
        detail = jobs_module.get_research_job(created["job_id"])
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()

    assert detail["status"] == "queued"
    assert detail["job_id"] == created["job_id"]


def test_sqlite_research_job_execution_hides_lease_metadata(monkeypatch, tmp_path) -> None:
    clear_live_env(monkeypatch)
    jobs_module.configure_research_jobs_sqlite_backend(tmp_path / "jobs.sqlite3")
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(
        api_module,
        "run_research",
        lambda query: make_api_state(query),
    )

    try:
        client = TestClient(api_module.app)
        response = client.post(
            "/research/jobs",
            json={"query": "SQLite lease smoke", "preset": "offline"},
        )
        assert response.status_code == 202
        detail_response = client.get(f"/research/jobs/{response.json()['job_id']}")
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "succeeded"
    assert "worker_id" not in detail
    assert "lease_expires_at" not in detail
    assert "heartbeat_at" not in detail
    assert "attempt_count" not in detail


def make_api_state(query: str) -> GraphState:
    return GraphState(
        user_request=query,
        report_markdown="# InsightGraph Research Report\n",
        findings=[
            Finding(
                title="Packaging differs",
                summary="Cursor and Copilot use different packaging signals.",
                evidence_ids=["cursor-pricing"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Cursor",
                positioning="Official product positioning signal",
                strengths=["Official/documented source coverage"],
                evidence_ids=["cursor-pricing"],
            )
        ],
        critique=Critique(passed=True, reason="Findings cite verified evidence."),
        tool_call_log=[
            ToolCallRecord(
                subtask_id="collect",
                tool_name="mock_search",
                query=query,
                evidence_count=1,
            )
        ],
        llm_call_log=[
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay-model",
                success=True,
                duration_ms=12,
            )
        ],
        iterations=1,
    )


def timestamp_sequence(*values: str):
    iterator = iter(values)
    return lambda: next(iterator)


def require_research_job_record(job_id: str) -> jobs_module.ResearchJob:
    job = jobs_module.get_research_job_record(job_id)
    assert job is not None
    return job


def without_progress_fields(payload: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in payload.items()
        if key
        not in {
            "progress_stage",
            "progress_percent",
            "progress_steps",
            "runtime_seconds",
            "tool_call_count",
            "llm_call_count",
        }
    }


def test_health_returns_ok() -> None:
    client = TestClient(api_module.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_remains_public_when_api_key_is_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_returns_html() -> None:
    client = TestClient(api_module.app)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "InsightGraph Dashboard" in response.text
    assert "data-insightgraph-dashboard" in response.text
    assert "id=\"dashboard-root\"" in response.text
    assert "id=\"query-input\"" in response.text
    assert "id=\"job-list\"" in response.text
    assert "id=\"report-panel\"" in response.text
    assert "progress-timeline" in response.text
    assert "download-md" in response.text
    assert "download-html" in response.text
    assert "renderProgressTimeline" in response.text
    assert "downloadReport" in response.text
    assert "connectJobStream" in response.text
    assert "closeJobStream" in response.text
    assert "WebSocket" in response.text
    assert "/stream" in response.text
    assert "'/research/jobs'" in response.text
    assert "'/research/jobs/summary'" in response.text
    assert "`/research/jobs/${encodeURIComponent(state.selectedJobId)}`" in response.text


def test_dashboard_remains_public_when_api_key_is_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "InsightGraph Dashboard" in response.text


def test_research_allows_requests_when_api_key_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_API_KEY", raising=False)

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "Compare AI coding agents"})

    assert response.status_code == 200
    assert response.json()["user_request"] == "Compare AI coding agents"


def test_research_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "Compare AI coding agents"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_rejects_wrong_bearer_api_key(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        headers={"Authorization": "Bearer wrong-key"},
        json={"query": "Compare AI coding agents"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_rejects_malformed_authorization(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        headers={"Authorization": "Token demo-key"},
        json={"query": "Compare AI coding agents"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_accepts_bearer_api_key(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        headers={"Authorization": "Bearer demo-key"},
        json={"query": "Compare AI coding agents"},
    )

    assert response.status_code == 200
    assert response.json()["user_request"] == "Compare AI coding agents"


def test_research_accepts_x_api_key(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        headers={"X-API-Key": "demo-key"},
        json={"query": "Compare AI coding agents"},
    )

    assert response.status_code == 200
    assert response.json()["user_request"] == "Compare AI coding agents"


def test_research_accepts_matching_key_when_other_header_is_wrong(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        headers={"Authorization": "Bearer wrong-key", "X-API-Key": "demo-key"},
        json={"query": "Compare AI coding agents"},
    )

    assert response.status_code == 200
    assert response.json()["user_request"] == "Compare AI coding agents"


def test_research_jobs_create_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", FakeExecutor())
    client = TestClient(api_module.app)

    response = client.post(
        "/research/jobs",
        json={"query": "Compare AI coding agents", "preset": "offline"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_jobs_create_accepts_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    client = TestClient(api_module.app)

    response = client.post(
        "/research/jobs",
        headers={"X-API-Key": "demo-key"},
        json={"query": "Compare AI coding agents", "preset": "offline"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert len(fake_executor.submissions) == 1


def test_research_jobs_list_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.get("/research/jobs")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_jobs_summary_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.get("/research/jobs/summary")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_job_detail_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.get("/research/jobs/job-123")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_job_report_export_rejects_missing_api_key_when_configured(
    monkeypatch,
) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.get("/research/jobs/job-123/report.md")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_job_stream_rejects_missing_api_key_when_configured(
    monkeypatch,
) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/research/jobs/job-123/stream"):
            pass

    assert exc_info.value.code == 1008


def test_research_job_cancel_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.post("/research/jobs/job-123/cancel")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_job_retry_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.post("/research/jobs/job-123/retry")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_create_app_returns_configured_fastapi_app() -> None:
    app = api_module.create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_module_level_app_remains_configured() -> None:
    route_paths = {route.path for route in api_module.app.routes}

    assert "/dashboard" in route_paths
    assert "/health" in route_paths
    assert "/research/jobs" in route_paths
    assert "/research/jobs/{job_id}" in route_paths
    assert "/research/jobs/{job_id}/report.md" in route_paths
    assert "/research/jobs/{job_id}/report.html" in route_paths
    assert "/research/jobs/{job_id}/stream" in route_paths


def test_current_utc_timestamp_uses_z_suffix() -> None:
    timestamp = api_module._current_utc_timestamp()

    assert timestamp.endswith("Z")
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert parsed.tzinfo == UTC


def test_research_job_routes_document_response_models_in_openapi() -> None:
    api_module.app.openapi_schema = None

    schema = api_module.app.openapi()
    paths = schema["paths"]
    create_operation = paths["/research/jobs"]["post"]
    list_operation = paths["/research/jobs"]["get"]
    summary_operation = paths["/research/jobs/summary"]["get"]
    detail_operation = paths["/research/jobs/{job_id}"]["get"]
    cancel_operation = paths["/research/jobs/{job_id}/cancel"]["post"]
    job_operations = [
        create_operation,
        list_operation,
        summary_operation,
        detail_operation,
        cancel_operation,
    ]

    for operation in job_operations:
        assert operation["tags"] == ["research jobs"]
        assert operation["summary"]
        assert operation["description"]

    assert create_operation["responses"]["202"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ResearchJobCreateResponse"}
    assert list_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ResearchJobsListResponse"}
    assert summary_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ResearchJobsSummaryResponse"}
    assert detail_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ResearchJobDetailResponse"}
    assert cancel_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ResearchJobDetailResponse"}

    assert create_operation["responses"]["202"]["content"]["application/json"][
        "example"
    ] == {
        "job_id": "job-123",
        "status": "queued",
        "created_at": "2026-04-27T10:00:00Z",
    }
    assert list_operation["responses"]["200"]["content"]["application/json"][
        "example"
    ] == {
        "jobs": [
            {
                "job_id": "job-123",
                "status": "queued",
                "query": "Compare AI coding agents",
                "preset": "offline",
                "created_at": "2026-04-27T10:00:00Z",
                "queue_position": 1,
            }
        ],
        "count": 1,
    }
    assert summary_operation["responses"]["200"]["content"]["application/json"][
        "example"
    ] == {
        "counts": {
            "queued": 1,
            "running": 1,
            "succeeded": 0,
            "failed": 0,
            "cancelled": 0,
            "total": 2,
        },
        "active_count": 2,
        "active_limit": 100,
        "queued_jobs": [
            {
                "job_id": "job-123",
                "status": "queued",
                "query": "Compare AI coding agents",
                "preset": "offline",
                "created_at": "2026-04-27T10:00:00Z",
                "queue_position": 1,
            }
        ],
        "running_jobs": [
            {
                "job_id": "job-456",
                "status": "running",
                "query": "Analyze market signals",
                "preset": "offline",
                "created_at": "2026-04-27T10:01:00Z",
                "started_at": "2026-04-27T10:01:01Z",
            }
        ],
    }
    assert detail_operation["responses"]["200"]["content"]["application/json"][
        "example"
    ] == {
        "job_id": "job-789",
        "status": "succeeded",
        "created_at": "2026-04-27T10:02:00Z",
        "started_at": "2026-04-27T10:02:01Z",
        "finished_at": "2026-04-27T10:02:05Z",
        "result": {"report_markdown": "# InsightGraph Research Report\n"},
    }
    assert cancel_operation["responses"]["200"]["content"]["application/json"][
        "example"
    ] == {
        "job_id": "job-123",
        "status": "cancelled",
        "created_at": "2026-04-27T10:00:00Z",
        "finished_at": "2026-04-27T10:00:10Z",
    }

    assert create_operation["responses"]["429"]["content"]["application/json"][
        "example"
    ] == {"detail": "Too many active research jobs."}
    assert create_operation["responses"]["500"]["content"]["application/json"][
        "example"
    ] == {"detail": "Research job store failed."}
    assert detail_operation["responses"]["404"]["content"]["application/json"][
        "example"
    ] == {"detail": "Research job not found."}
    assert cancel_operation["responses"]["404"]["content"]["application/json"][
        "example"
    ] == {"detail": "Research job not found."}
    assert cancel_operation["responses"]["409"]["content"]["application/json"][
        "example"
    ] == {"detail": "Only queued research jobs can be cancelled."}
    assert cancel_operation["responses"]["500"]["content"]["application/json"][
        "example"
    ] == {"detail": "Research job store failed."}

    list_parameters = list_operation["parameters"]
    assert list_parameters == [
        {
            "name": "status",
            "in": "query",
            "required": False,
            "description": "Filter jobs by status. Omit to return all retained jobs.",
            "schema": {
                "anyOf": [
                    {
                        "enum": [
                            "queued",
                            "running",
                            "succeeded",
                            "failed",
                            "cancelled",
                        ],
                        "type": "string",
                    },
                    {"type": "null"},
                ],
                "description": "Filter jobs by status. Omit to return all retained jobs.",
                "title": "Status",
            },
        },
        {
            "name": "limit",
            "in": "query",
            "required": False,
            "description": (
                "Maximum number of jobs to return. The response count is the "
                "returned count, not a total."
            ),
            "schema": {
                "default": 100,
                "description": (
                    "Maximum number of jobs to return. The response count is the "
                    "returned count, not a total."
                ),
                "maximum": 100,
                "minimum": 1,
                "title": "Limit",
                "type": "integer",
            },
        },
    ]

    components = schema["components"]["schemas"]
    assert components["ResearchJobCreateResponse"]["required"] == [
        "job_id",
        "status",
        "created_at",
    ]
    assert components["ResearchJobSummary"]["required"] == [
        "job_id",
        "status",
        "query",
        "preset",
        "created_at",
    ]
    assert components["ResearchJobsListResponse"]["properties"]["jobs"] == {
        "items": {"$ref": "#/components/schemas/ResearchJobSummary"},
        "title": "Jobs",
        "type": "array",
    }
    assert components["ResearchJobsSummaryResponse"]["properties"]["queued_jobs"] == {
        "items": {"$ref": "#/components/schemas/ResearchJobSummary"},
        "title": "Queued Jobs",
        "type": "array",
    }
    for schema_name, optional_fields in {
        "ResearchJobSummary": ["started_at", "finished_at", "queue_position"],
        "ResearchJobDetailResponse": [
            "started_at",
            "finished_at",
            "queue_position",
            "result",
            "error",
        ],
    }.items():
        properties = components[schema_name]["properties"]
        for field_name in optional_fields:
            assert {"type": "null"} not in properties[field_name].get("anyOf", [])


def test_research_returns_cli_aligned_json(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "  Compare AI coding agents  "})

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_request"] == "Compare AI coding agents"
    assert payload["report_markdown"] == "# InsightGraph Research Report\n"
    assert payload["findings"] == [
        {
            "title": "Packaging differs",
            "summary": "Cursor and Copilot use different packaging signals.",
            "evidence_ids": ["cursor-pricing"],
        }
    ]
    assert payload["competitive_matrix"] == [
        {
            "product": "Cursor",
            "positioning": "Official product positioning signal",
            "strengths": ["Official/documented source coverage"],
            "evidence_ids": ["cursor-pricing"],
        }
    ]
    assert payload["critique"] == {
        "passed": True,
        "reason": "Findings cite verified evidence.",
        "missing_topics": [],
    }
    assert payload["tool_call_log"][0]["tool_name"] == "mock_search"
    assert payload["llm_call_log"][0]["model"] == "relay-model"
    assert payload["iterations"] == 1


def test_research_passes_query_to_workflow(monkeypatch) -> None:
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "Compare Cursor"})

    assert response.status_code == 200
    assert observed_queries == ["Compare Cursor"]


def test_research_enters_environment_lock(monkeypatch) -> None:
    lock_events: list[str] = []

    class FakeLock:
        def __enter__(self) -> None:
            lock_events.append("enter")

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            lock_events.append("exit")

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_RESEARCH_ENV_LOCK", FakeLock())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "Compare Cursor"})

    assert response.status_code == 200
    assert lock_events == ["enter", "exit"]


def test_research_live_llm_preset_restores_env(monkeypatch) -> None:
    clear_live_env(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update({name: os.getenv(name) for name in LIVE_LLM_PRESET_DEFAULTS})
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        json={"query": "Compare AI coding agents", "preset": "live-llm"},
    )

    assert response.status_code == 200
    assert observed_env == LIVE_LLM_PRESET_DEFAULTS
    assert {name: os.getenv(name) for name in LIVE_LLM_PRESET_DEFAULTS} == {
        name: None for name in LIVE_LLM_PRESET_DEFAULTS
    }


def test_research_live_llm_preset_restores_explicit_env(monkeypatch) -> None:
    clear_live_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "deterministic")
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update({name: os.getenv(name) for name in LIVE_LLM_PRESET_DEFAULTS})
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        json={"query": "Compare AI coding agents", "preset": "live-llm"},
    )

    assert response.status_code == 200
    assert observed_env["INSIGHT_GRAPH_SEARCH_PROVIDER"] == "mock"
    assert observed_env["INSIGHT_GRAPH_REPORTER_PROVIDER"] == "deterministic"
    assert observed_env["INSIGHT_GRAPH_USE_WEB_SEARCH"] == "1"
    assert observed_env["INSIGHT_GRAPH_ANALYST_PROVIDER"] == "llm"
    assert os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER") == "mock"
    assert os.getenv("INSIGHT_GRAPH_REPORTER_PROVIDER") == "deterministic"
    assert os.getenv("INSIGHT_GRAPH_USE_WEB_SEARCH") is None


def test_research_offline_preset_does_not_apply_live_defaults(monkeypatch) -> None:
    clear_live_env(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update({name: os.getenv(name) for name in LIVE_LLM_PRESET_DEFAULTS})
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        json={"query": "Compare AI coding agents", "preset": "offline"},
    )

    assert response.status_code == 200
    assert observed_env == {name: None for name in LIVE_LLM_PRESET_DEFAULTS}


def test_research_offline_preset_preserves_explicit_env(monkeypatch) -> None:
    clear_live_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update({name: os.getenv(name) for name in LIVE_LLM_PRESET_DEFAULTS})
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        json={"query": "Compare AI coding agents", "preset": "offline"},
    )

    assert response.status_code == 200
    assert observed_env["INSIGHT_GRAPH_SEARCH_PROVIDER"] == "mock"
    assert os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER") == "mock"
    assert observed_env["INSIGHT_GRAPH_USE_WEB_SEARCH"] is None


def test_research_rejects_blank_query() -> None:
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "   "})

    assert response.status_code == 422


def test_research_rejects_unknown_preset() -> None:
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        json={"query": "Compare AI coding agents", "preset": "bad"},
    )

    assert response.status_code == 422


def test_research_restores_env_after_workflow_exception(monkeypatch) -> None:
    clear_live_env(monkeypatch)

    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider payload and local path")

    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        json={"query": "Compare AI coding agents", "preset": "live-llm"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Research workflow failed."}
    assert "secret provider payload" not in response.text
    assert "local path" not in response.text
    assert {name: os.getenv(name) for name in LIVE_LLM_PRESET_DEFAULTS} == {
        name: None for name in LIVE_LLM_PRESET_DEFAULTS
    }


def test_research_safe_500_does_not_log_raw_exception(monkeypatch, caplog) -> None:
    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider payload and local path")

    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "Compare AI coding agents"})

    assert response.status_code == 500
    assert "secret provider payload" not in caplog.text
    assert "local path" not in caplog.text


def test_create_research_job_returns_queued_job(monkeypatch) -> None:
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    response = client.post("/research/jobs", json={"query": "Compare Cursor"})

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert isinstance(payload["job_id"], str)
    assert len(fake_executor.submissions) == 1


def test_retry_research_job_endpoint_creates_and_schedules_new_job(monkeypatch) -> None:
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    source = jobs_module.ResearchJob(
        id="failed-job",
        query="Retry via API",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="failed",
        finished_at="2026-04-28T10:00:01Z",
        error="Research workflow failed.",
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    response = TestClient(api_module.app).post("/research/jobs/failed-job/retry")

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["job_id"] != "failed-job"
    assert fake_executor.submissions == [(api_module._run_research_job, (payload["job_id"],))]


def test_retry_research_job_endpoint_rejects_running_job() -> None:
    source = jobs_module.ResearchJob(
        id="running-job",
        query="Running",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="running",
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    response = TestClient(api_module.app).post("/research/jobs/running-job/retry")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Only failed or cancelled research jobs can be retried."
    }


def test_retry_research_job_endpoint_respects_active_cap() -> None:
    source = jobs_module.ResearchJob(
        id="failed-job",
        query="Retry over cap",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="failed",
        finished_at="2026-04-28T10:00:01Z",
        error="Research workflow failed.",
    )
    active = jobs_module.ResearchJob(
        id="active-job",
        query="Active",
        preset=api_module.ResearchPreset.offline,
        created_order=2,
        created_at="2026-04-28T10:00:02Z",
    )
    jobs_module.reset_research_jobs_state(
        next_job_sequence=2,
        active_limit=1,
        jobs=[source, active],
    )

    response = TestClient(api_module.app).post("/research/jobs/failed-job/retry")

    assert response.status_code == 429
    assert response.json() == {"detail": "Too many active research jobs."}


def test_create_research_job_rejects_when_active_job_limit_reached(
    monkeypatch,
) -> None:
    fake_executor = FakeExecutor()
    jobs_module.reset_research_jobs_state(active_limit=2)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    client = TestClient(api_module.app)

    first = client.post("/research/jobs", json={"query": "First"})
    second = client.post("/research/jobs", json={"query": "Second"})
    response = client.post("/research/jobs", json={"query": "Third"})

    assert first.status_code == 202
    assert second.status_code == 202
    next_sequence = jobs_module.get_next_research_job_sequence()
    assert response.status_code == 429
    assert response.json() == {"detail": "Too many active research jobs."}
    assert jobs_module.get_next_research_job_sequence() == next_sequence
    assert len(fake_executor.submissions) == 2
    assert client.get("/research/jobs").json()["count"] == 2


def test_create_research_job_active_limit_ignores_terminal_jobs(monkeypatch) -> None:
    def succeed_run_research(query: str) -> GraphState:
        return make_api_state(query)

    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("provider failed")

    jobs_module.reset_research_jobs_state(active_limit=1)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", succeed_run_research)
    client = TestClient(api_module.app)

    succeeded = client.post("/research/jobs", json={"query": "Succeeded"})
    second = client.post("/research/jobs", json={"query": "Second"})

    assert succeeded.status_code == 202
    assert second.status_code == 202

    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    failed = client.post("/research/jobs", json={"query": "Failed"})
    after_failed = client.post("/research/jobs", json={"query": "After failed"})

    assert failed.status_code == 202
    assert after_failed.status_code == 202

    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    cancelled = client.post("/research/jobs", json={"query": "Cancelled"})
    cancelled_job_id = cancelled.json()["job_id"]
    assert client.post(f"/research/jobs/{cancelled_job_id}/cancel").status_code == 200
    after_cancel = client.post("/research/jobs", json={"query": "After cancel"})

    assert cancelled.status_code == 202
    assert after_cancel.status_code == 202


def test_create_research_job_response_stays_queued_if_executor_runs_immediately(
    monkeypatch,
) -> None:
    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    response = client.post("/research/jobs", json={"query": "Compare Cursor"})

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    job_response = client.get(f"/research/jobs/{payload['job_id']}")
    assert job_response.json()["status"] == "succeeded"


def test_get_research_job_includes_progress_metadata_for_queued_job() -> None:
    jobs_module.reset_research_jobs_state()
    job = jobs_module.ResearchJob(
        id="queued-job",
        query="Queued progress",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
    )
    jobs_module.seed_research_job(job, next_job_sequence=1)

    response = TestClient(api_module.app).get("/research/jobs/queued-job")

    assert response.status_code == 200
    payload = response.json()
    assert payload["progress_stage"] == "queued"
    assert payload["progress_percent"] == 0
    assert payload["runtime_seconds"] == 0
    assert payload["tool_call_count"] == 0
    assert payload["llm_call_count"] == 0
    assert payload["progress_steps"] == [
        {"id": "planner", "label": "Planner", "status": "pending"},
        {"id": "collector", "label": "Collector", "status": "pending"},
        {"id": "analyst", "label": "Analyst", "status": "pending"},
        {"id": "critic", "label": "Critic", "status": "pending"},
        {"id": "reporter", "label": "Reporter", "status": "pending"},
    ]


def test_get_research_job_includes_progress_metadata_for_running_job() -> None:
    jobs_module.reset_research_jobs_state()
    job = jobs_module.ResearchJob(
        id="running-job",
        query="Running progress",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        started_at="2026-04-28T10:00:05Z",
        status="running",
    )
    jobs_module.seed_research_job(job, next_job_sequence=1)

    response = TestClient(api_module.app).get("/research/jobs/running-job")

    assert response.status_code == 200
    payload = response.json()
    assert payload["progress_stage"] == "planner"
    assert payload["progress_percent"] == 20
    assert payload["runtime_seconds"] == 0
    assert payload["progress_steps"][0] == {
        "id": "planner",
        "label": "Planner",
        "status": "active",
    }


def test_get_research_job_includes_progress_metadata_for_succeeded_job() -> None:
    result = api_module._build_research_json_payload(make_api_state("Succeeded progress"))
    jobs_module.reset_research_jobs_state()
    job = jobs_module.ResearchJob(
        id="succeeded-job",
        query="Succeeded progress",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        started_at="2026-04-28T10:00:05Z",
        finished_at="2026-04-28T10:00:17Z",
        status="succeeded",
        result=result,
    )
    jobs_module.seed_research_job(job, next_job_sequence=1)

    response = TestClient(api_module.app).get("/research/jobs/succeeded-job")

    assert response.status_code == 200
    payload = response.json()
    assert payload["progress_stage"] == "completed"
    assert payload["progress_percent"] == 100
    assert payload["runtime_seconds"] == 12
    assert payload["tool_call_count"] == 1
    assert payload["llm_call_count"] == 1
    assert {step["status"] for step in payload["progress_steps"]} == {"completed"}


def test_get_research_job_includes_progress_metadata_for_failed_job() -> None:
    jobs_module.reset_research_jobs_state()
    job = jobs_module.ResearchJob(
        id="failed-job",
        query="Failed progress",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        started_at="2026-04-28T10:00:05Z",
        finished_at="2026-04-28T10:00:08Z",
        status="failed",
        error="Research workflow failed.",
    )
    jobs_module.seed_research_job(job, next_job_sequence=1)

    response = TestClient(api_module.app).get("/research/jobs/failed-job")

    assert response.status_code == 200
    payload = response.json()
    assert payload["progress_stage"] == "failed"
    assert payload["progress_percent"] == 100
    assert payload["runtime_seconds"] == 3
    assert payload["progress_steps"][0]["status"] == "failed"


def test_get_research_job_includes_progress_metadata_for_cancelled_job() -> None:
    jobs_module.reset_research_jobs_state()
    job = jobs_module.ResearchJob(
        id="cancelled-job",
        query="Cancelled progress",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        finished_at="2026-04-28T10:00:04Z",
        status="cancelled",
    )
    jobs_module.seed_research_job(job, next_job_sequence=1)

    response = TestClient(api_module.app).get("/research/jobs/cancelled-job")

    assert response.status_code == 200
    payload = response.json()
    assert payload["progress_stage"] == "cancelled"
    assert payload["progress_percent"] == 100
    assert payload["runtime_seconds"] == 4
    assert {step["status"] for step in payload["progress_steps"]} == {"skipped"}


def test_research_job_stream_sends_job_snapshot() -> None:
    jobs_module.reset_research_jobs_state()
    job = jobs_module.ResearchJob(
        id="stream-job",
        query="Stream progress",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
    )
    jobs_module.seed_research_job(job, next_job_sequence=1)
    client = TestClient(api_module.app)

    with client.websocket_connect("/research/jobs/stream-job/stream") as websocket:
        event = websocket.receive_json()

    assert event["type"] == "job_snapshot"
    assert event["job"]["job_id"] == "stream-job"
    assert event["job"]["progress_stage"] == "queued"


def test_research_job_stream_sends_error_for_unknown_job() -> None:
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    with client.websocket_connect("/research/jobs/missing/stream") as websocket:
        event = websocket.receive_json()

    assert event == {"type": "error", "detail": "Research job not found."}


def test_research_job_stream_accepts_api_key_query_param(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    jobs_module.reset_research_jobs_state()
    job = jobs_module.ResearchJob(
        id="protected-stream-job",
        query="Protected stream",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
    )
    jobs_module.seed_research_job(job, next_job_sequence=1)
    client = TestClient(api_module.app)

    with client.websocket_connect(
        "/research/jobs/protected-stream-job/stream?api_key=demo-key"
    ) as websocket:
        event = websocket.receive_json()

    assert event["type"] == "job_snapshot"
    assert event["job"]["job_id"] == "protected-stream-job"


def test_research_job_includes_created_at_until_started(monkeypatch) -> None:
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        lambda: "2026-04-27T10:00:00Z",
    )
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    response = client.post("/research/jobs", json={"query": "Compare Cursor"})

    assert response.status_code == 202
    payload = response.json()
    job_id = payload["job_id"]
    assert payload == {
        "job_id": job_id,
        "status": "queued",
        "created_at": "2026-04-27T10:00:00Z",
    }
    assert without_progress_fields(client.get(f"/research/jobs/{job_id}").json()) == {
        "job_id": job_id,
        "status": "queued",
        "created_at": "2026-04-27T10:00:00Z",
        "queue_position": 1,
    }


def test_research_job_detail_includes_queue_position_for_queued_jobs(
    monkeypatch,
) -> None:
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence(
            "2026-04-27T09:00:00Z",
            "2026-04-27T09:00:01Z",
            "2026-04-27T09:00:02Z",
        ),
    )
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    first = client.post("/research/jobs", json={"query": "First"}).json()["job_id"]
    running = client.post("/research/jobs", json={"query": "Running"}).json()[
        "job_id"
    ]
    third = client.post("/research/jobs", json={"query": "Third"}).json()["job_id"]
    jobs_module.update_research_job_record(
        running,
        status="running",
        started_at="2026-04-27T09:00:03Z",
    )

    assert without_progress_fields(client.get(f"/research/jobs/{first}").json()) == {
        "job_id": first,
        "status": "queued",
        "created_at": "2026-04-27T09:00:00Z",
        "queue_position": 1,
    }
    assert without_progress_fields(client.get(f"/research/jobs/{running}").json()) == {
        "job_id": running,
        "status": "running",
        "created_at": "2026-04-27T09:00:01Z",
        "started_at": "2026-04-27T09:00:03Z",
    }
    assert without_progress_fields(client.get(f"/research/jobs/{third}").json()) == {
        "job_id": third,
        "status": "queued",
        "created_at": "2026-04-27T09:00:02Z",
        "queue_position": 2,
    }


def test_get_research_job_returns_success_result(monkeypatch) -> None:
    fake_executor = FakeExecutor()
    observed_queries: list[str] = []
    job_id = ""

    def fake_run_research(query: str) -> GraphState:
        job = require_research_job_record(job_id)
        assert job.started_at == "2026-04-27T10:00:01Z"
        assert job.finished_at is None
        observed_queries.append(query)
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence(
            "2026-04-27T10:00:00Z",
            "2026-04-27T10:00:01Z",
            "2026-04-27T10:00:02Z",
        ),
    )
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    create_response = client.post("/research/jobs", json={"query": "  Compare Cursor  "})
    job_id = create_response.json()["job_id"]

    queued_response = client.get(f"/research/jobs/{job_id}")
    assert queued_response.status_code == 200
    assert without_progress_fields(queued_response.json()) == {
        "job_id": job_id,
        "status": "queued",
        "created_at": "2026-04-27T10:00:00Z",
        "queue_position": 1,
    }

    fake_executor.run_next()

    response = client.get(f"/research/jobs/{job_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["status"] == "succeeded"
    assert payload["created_at"] == "2026-04-27T10:00:00Z"
    assert payload["started_at"] == "2026-04-27T10:00:01Z"
    assert payload["finished_at"] == "2026-04-27T10:00:02Z"
    assert payload["result"]["user_request"] == "Compare Cursor"
    assert payload["result"]["competitive_matrix"][0]["product"] == "Cursor"
    assert observed_queries == ["Compare Cursor"]


def test_get_research_job_returns_safe_failure(monkeypatch) -> None:
    fake_executor = FakeExecutor()

    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider payload")

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence(
            "2026-04-27T11:00:00Z",
            "2026-04-27T11:00:01Z",
            "2026-04-27T11:00:02Z",
        ),
    )
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    create_response = client.post("/research/jobs", json={"query": "Compare Cursor"})
    job_id = create_response.json()["job_id"]
    fake_executor.run_next()

    response = client.get(f"/research/jobs/{job_id}")

    assert response.status_code == 200
    assert without_progress_fields(response.json()) == {
        "job_id": job_id,
        "status": "failed",
        "created_at": "2026-04-27T11:00:00Z",
        "started_at": "2026-04-27T11:00:01Z",
        "finished_at": "2026-04-27T11:00:02Z",
        "error": "Research workflow failed.",
    }
    assert "secret provider payload" not in response.text


def test_get_research_job_returns_404_for_unknown_job() -> None:
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    response = client.get("/research/jobs/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Research job not found."}


def test_research_job_markdown_report_export_returns_completed_report() -> None:
    result = api_module._build_research_json_payload(make_api_state("Export report"))
    jobs_module.reset_research_jobs_state()
    jobs_module.seed_research_job(
        jobs_module.ResearchJob(
            id="report-job",
            query="Export report",
            preset=api_module.ResearchPreset.offline,
            created_order=1,
            created_at="2026-04-28T10:00:00Z",
            started_at="2026-04-28T10:00:01Z",
            finished_at="2026-04-28T10:00:02Z",
            status="succeeded",
            result=result,
        ),
        next_job_sequence=1,
    )

    response = TestClient(api_module.app).get("/research/jobs/report-job/report.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert response.text == "# InsightGraph Research Report\n"


def test_research_job_html_report_export_escapes_report_content() -> None:
    jobs_module.reset_research_jobs_state()
    jobs_module.seed_research_job(
        jobs_module.ResearchJob(
            id="html-report-job",
            query="HTML report",
            preset=api_module.ResearchPreset.offline,
            created_order=1,
            created_at="2026-04-28T10:00:00Z",
            started_at="2026-04-28T10:00:01Z",
            finished_at="2026-04-28T10:00:02Z",
            status="succeeded",
            result={"report_markdown": "# Safe\n\n<script>alert('x')</script>\n"},
        ),
        next_job_sequence=1,
    )

    response = TestClient(api_module.app).get("/research/jobs/html-report-job/report.html")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>Safe</h1>" in response.text
    assert "<script>alert" not in response.text
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in response.text


def test_research_job_report_export_rejects_jobs_without_report() -> None:
    jobs_module.reset_research_jobs_state()
    jobs_module.seed_research_job(
        jobs_module.ResearchJob(
            id="queued-report-job",
            query="No report",
            preset=api_module.ResearchPreset.offline,
            created_order=1,
            created_at="2026-04-28T10:00:00Z",
        ),
        next_job_sequence=1,
    )

    response = TestClient(api_module.app).get("/research/jobs/queued-report-job/report.md")

    assert response.status_code == 409
    assert response.json() == {"detail": "Research job report is not available."}


def test_research_job_report_export_returns_404_for_unknown_job() -> None:
    jobs_module.reset_research_jobs_state()

    response = TestClient(api_module.app).get("/research/jobs/missing/report.md")

    assert response.status_code == 404
    assert response.json() == {"detail": "Research job not found."}


def test_cancel_research_job_cancels_queued_job(monkeypatch) -> None:
    fake_executor = FakeExecutor()
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence("2026-04-27T12:00:00Z", "2026-04-27T12:00:01Z"),
    )
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    job_id = client.post("/research/jobs", json={"query": "Cancel me"}).json()[
        "job_id"
    ]

    response = client.post(f"/research/jobs/{job_id}/cancel")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": job_id,
        "status": "cancelled",
        "created_at": "2026-04-27T12:00:00Z",
        "finished_at": "2026-04-27T12:00:01Z",
    }
    assert without_progress_fields(client.get(f"/research/jobs/{job_id}").json()) == {
        "job_id": job_id,
        "status": "cancelled",
        "created_at": "2026-04-27T12:00:00Z",
        "finished_at": "2026-04-27T12:00:01Z",
    }

    fake_executor.run_next()

    assert observed_queries == []
    assert client.get(f"/research/jobs/{job_id}").json()["status"] == "cancelled"


def test_cancel_research_job_returns_404_for_unknown_job() -> None:
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    response = client.post("/research/jobs/missing/cancel")

    assert response.status_code == 404
    assert response.json() == {"detail": "Research job not found."}


def test_cancel_research_job_rejects_running_or_finished_jobs(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    job_id = client.post("/research/jobs", json={"query": "Finished"}).json()[
        "job_id"
    ]

    jobs_module.update_research_job_record(job_id, status="running")
    running_response = client.post(f"/research/jobs/{job_id}/cancel")
    assert running_response.status_code == 409
    assert running_response.json() == {
        "detail": "Only queued research jobs can be cancelled."
    }

    jobs_module.update_research_job_record(job_id, status="succeeded")
    succeeded_response = client.post(f"/research/jobs/{job_id}/cancel")
    assert succeeded_response.status_code == 409
    assert succeeded_response.json() == {
        "detail": "Only queued research jobs can be cancelled."
    }

    jobs_module.update_research_job_record(job_id, status="failed")
    failed_response = client.post(f"/research/jobs/{job_id}/cancel")
    assert failed_response.status_code == 409
    assert failed_response.json() == {
        "detail": "Only queued research jobs can be cancelled."
    }


def test_list_research_jobs_returns_summaries_newest_first(monkeypatch) -> None:
    fake_executor = FakeExecutor()

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence(
            "2026-04-27T13:00:00Z",
            "2026-04-27T13:00:01Z",
            "2026-04-27T13:00:02Z",
            "2026-04-27T13:00:03Z",
            "2026-04-27T13:00:05Z",
            "2026-04-27T13:00:06Z",
            "2026-04-27T13:00:07Z",
            "2026-04-27T13:00:08Z",
            "2026-04-27T13:00:09Z",
            "2026-04-27T13:00:10Z",
        ),
    )
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    cancelled = client.post("/research/jobs", json={"query": "Cancelled"}).json()[
        "job_id"
    ]
    cancel_response = client.post(f"/research/jobs/{cancelled}/cancel")
    assert cancel_response.status_code == 200

    queued = client.post("/research/jobs", json={"query": "Queued"}).json()["job_id"]
    running = client.post("/research/jobs", json={"query": "Running"}).json()["job_id"]
    jobs_module.update_research_job_record(
        running,
        status="running",
        started_at="2026-04-27T13:00:04Z",
    )

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    succeeded = client.post("/research/jobs", json={"query": "Succeeded"}).json()[
        "job_id"
    ]

    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider payload")

    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    failed = client.post("/research/jobs", json={"query": "Failed"}).json()["job_id"]

    response = client.get("/research/jobs")

    assert response.status_code == 200
    assert response.json() == {
        "jobs": [
            {
                "job_id": failed,
                "status": "failed",
                "query": "Failed",
                "preset": "offline",
                "created_at": "2026-04-27T13:00:08Z",
                "started_at": "2026-04-27T13:00:09Z",
                "finished_at": "2026-04-27T13:00:10Z",
            },
            {
                "job_id": succeeded,
                "status": "succeeded",
                "query": "Succeeded",
                "preset": "offline",
                "created_at": "2026-04-27T13:00:05Z",
                "started_at": "2026-04-27T13:00:06Z",
                "finished_at": "2026-04-27T13:00:07Z",
            },
            {
                "job_id": running,
                "status": "running",
                "query": "Running",
                "preset": "offline",
                "created_at": "2026-04-27T13:00:03Z",
                "started_at": "2026-04-27T13:00:04Z",
            },
            {
                "job_id": queued,
                "status": "queued",
                "query": "Queued",
                "preset": "offline",
                "created_at": "2026-04-27T13:00:02Z",
                "queue_position": 1,
            },
            {
                "job_id": cancelled,
                "status": "cancelled",
                "query": "Cancelled",
                "preset": "offline",
                "created_at": "2026-04-27T13:00:00Z",
                "finished_at": "2026-04-27T13:00:01Z",
            },
        ],
        "count": 5,
    }
    assert "secret provider payload" not in response.text
    assert "result" not in response.text
    assert "error" not in response.text


def test_list_research_jobs_filters_by_status(monkeypatch) -> None:
    fake_executor = FakeExecutor()

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence(
            "2026-04-27T18:00:00Z",
            "2026-04-27T18:00:01Z",
            "2026-04-27T18:00:02Z",
            "2026-04-27T18:00:03Z",
            "2026-04-27T18:00:04Z",
            "2026-04-27T18:00:05Z",
        ),
    )
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    queued = client.post("/research/jobs", json={"query": "Queued"}).json()["job_id"]
    running = client.post("/research/jobs", json={"query": "Running"}).json()["job_id"]
    jobs_module.update_research_job_record(
        running,
        status="running",
        started_at="2026-04-27T18:00:03Z",
    )

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    succeeded = client.post("/research/jobs", json={"query": "Succeeded"}).json()[
        "job_id"
    ]

    response = client.get("/research/jobs", params={"status": "queued"})

    assert response.status_code == 200
    assert response.json() == {
        "jobs": [
            {
                "job_id": queued,
                "status": "queued",
                "query": "Queued",
                "preset": "offline",
                "created_at": "2026-04-27T18:00:00Z",
                "queue_position": 1,
            }
        ],
        "count": 1,
    }
    assert running not in response.text
    assert succeeded not in response.text


def test_list_research_jobs_limits_newest_matching_jobs(monkeypatch) -> None:
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence(
            "2026-04-27T19:00:00Z",
            "2026-04-27T19:00:01Z",
            "2026-04-27T19:00:02Z",
        ),
    )
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    oldest = client.post("/research/jobs", json={"query": "Oldest"}).json()["job_id"]
    middle = client.post("/research/jobs", json={"query": "Middle"}).json()["job_id"]
    newest = client.post("/research/jobs", json={"query": "Newest"}).json()["job_id"]

    response = client.get("/research/jobs", params={"status": "queued", "limit": 2})

    assert response.status_code == 200
    assert response.json() == {
        "jobs": [
            {
                "job_id": newest,
                "status": "queued",
                "query": "Newest",
                "preset": "offline",
                "created_at": "2026-04-27T19:00:02Z",
                "queue_position": 3,
            },
            {
                "job_id": middle,
                "status": "queued",
                "query": "Middle",
                "preset": "offline",
                "created_at": "2026-04-27T19:00:01Z",
                "queue_position": 2,
            },
        ],
        "count": 2,
    }
    assert oldest not in response.text


def test_list_research_jobs_uses_default_limit() -> None:
    jobs_module.reset_research_jobs_state(
        jobs=[
            jobs_module.ResearchJob(
                id=f"job-{index}",
                query=f"Job {index}",
                preset=api_module.ResearchPreset.offline,
                created_order=index,
                created_at=f"2026-04-27T19:00:{index % 60:02d}Z",
            )
            for index in range(101)
        ]
    )
    client = TestClient(api_module.app)

    response = client.get("/research/jobs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 100
    assert len(payload["jobs"]) == 100
    assert payload["jobs"][0]["query"] == "Job 100"
    assert payload["jobs"][-1]["query"] == "Job 1"
    assert "Job 0" not in response.text


def test_list_research_jobs_rejects_invalid_status() -> None:
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    response = client.get("/research/jobs", params={"status": "unknown"})

    assert response.status_code == 422


def test_list_research_jobs_rejects_invalid_limits() -> None:
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    too_small = client.get("/research/jobs", params={"limit": 0})
    too_large = client.get("/research/jobs", params={"limit": 101})

    assert too_small.status_code == 422
    assert too_large.status_code == 422


def test_create_research_job_writes_configured_store(monkeypatch, tmp_path) -> None:
    store_path = tmp_path / "jobs.json"
    fake_executor = FakeExecutor()
    jobs_module.reset_research_jobs_state(store_path=store_path)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        lambda: "2026-04-27T20:00:00Z",
    )
    client = TestClient(api_module.app)

    response = client.post("/research/jobs", json={"query": "Persist me"})

    assert response.status_code == 202
    payload = store_path.read_text(encoding="utf-8")
    assert '"next_job_sequence"' in payload
    assert '"query": "Persist me"' in payload


def test_create_research_job_returns_safe_500_when_store_write_fails(
    monkeypatch,
    tmp_path,
) -> None:
    def fail_persist() -> None:
        raise jobs_module.ResearchJobsStoreError("secret path")

    store_path = tmp_path / "jobs.json"
    fake_executor = FakeExecutor()
    jobs_module.reset_research_jobs_state(store_path=store_path)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(jobs_module, "_persist_research_jobs_locked", fail_persist)
    client = TestClient(api_module.app)

    response = client.post("/research/jobs", json={"query": "Persist me"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Research job store failed."}
    assert "secret path" not in response.text
    assert fake_executor.submissions == []
    assert client.get("/research/jobs").json() == {"jobs": [], "count": 0}


def test_create_research_job_restores_pruned_jobs_when_store_write_fails(
    monkeypatch,
    tmp_path,
) -> None:
    def fail_persist() -> None:
        raise jobs_module.ResearchJobsStoreError("secret path")

    store_path = tmp_path / "jobs.json"
    existing = jobs_module.ResearchJob(
        id="existing-job",
        query="Existing",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
        status="succeeded",
        finished_at="2026-04-27T20:00:01Z",
    )
    fake_executor = FakeExecutor()
    jobs_module.reset_research_jobs_state(
        next_job_sequence=1,
        store_path=store_path,
        retained_limit=1,
        jobs=[existing],
    )
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(jobs_module, "_persist_research_jobs_locked", fail_persist)
    client = TestClient(api_module.app)

    response = client.post("/research/jobs", json={"query": "New"})

    assert response.status_code == 500
    assert jobs_module.get_next_research_job_sequence() == 1
    assert jobs_module.get_research_job_record("existing-job") == existing
    assert fake_executor.submissions == []


def test_cancel_research_job_rolls_back_when_store_write_fails(
    monkeypatch,
    tmp_path,
) -> None:
    def fail_persist() -> None:
        raise jobs_module.ResearchJobsStoreError("secret path")

    store_path = tmp_path / "jobs.json"
    job = jobs_module.ResearchJob(
        id="job-1",
        query="Cancel",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    jobs_module.reset_research_jobs_state(store_path=store_path, jobs=[job])
    monkeypatch.setattr(jobs_module, "_persist_research_jobs_locked", fail_persist)
    client = TestClient(api_module.app)

    response = client.post(f"/research/jobs/{job.id}/cancel")

    assert response.status_code == 500
    assert response.json() == {"detail": "Research job store failed."}
    stored = require_research_job_record(job.id)
    assert stored.status == "queued"
    assert stored.finished_at is None


def test_cancel_research_job_restores_pruned_jobs_when_store_write_fails(
    monkeypatch,
    tmp_path,
) -> None:
    def fail_persist() -> None:
        raise jobs_module.ResearchJobsStoreError("secret path")

    store_path = tmp_path / "jobs.json"
    old_finished = jobs_module.ResearchJob(
        id="old-finished",
        query="Old",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T19:00:00Z",
        status="succeeded",
        finished_at="2026-04-27T19:00:01Z",
    )
    queued = jobs_module.ResearchJob(
        id="queued-job",
        query="Cancel",
        preset=api_module.ResearchPreset.offline,
        created_order=2,
        created_at="2026-04-27T20:00:00Z",
    )
    jobs_module.reset_research_jobs_state(
        store_path=store_path,
        retained_limit=1,
        jobs=[old_finished, queued],
    )
    monkeypatch.setattr(jobs_module, "_persist_research_jobs_locked", fail_persist)
    client = TestClient(api_module.app)

    response = client.post(f"/research/jobs/{queued.id}/cancel")

    assert response.status_code == 500
    assert jobs_module.get_research_job_record("old-finished") == old_finished
    assert jobs_module.get_research_job_record("queued-job") == queued
    assert queued.status == "queued"
    assert queued.finished_at is None


def test_run_research_job_marks_failed_when_running_store_write_fails(
    monkeypatch,
    tmp_path,
) -> None:
    def fail_persist() -> None:
        raise jobs_module.ResearchJobsStoreError("secret path")

    def fail_if_called(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    store_path = tmp_path / "jobs.json"
    job = jobs_module.ResearchJob(
        id="job-1",
        query="Run",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    jobs_module.reset_research_jobs_state(store_path=store_path, jobs=[job])
    monkeypatch.setattr(jobs_module, "_persist_research_jobs_locked", fail_persist)
    monkeypatch.setattr(api_module, "run_research", fail_if_called)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence("2026-04-27T20:00:01Z", "2026-04-27T20:00:02Z"),
    )

    api_module._run_research_job(job.id)

    stored = require_research_job_record(job.id)
    assert stored.status == "failed"
    assert stored.started_at == "2026-04-27T20:00:01Z"
    assert stored.finished_at == "2026-04-27T20:00:02Z"
    assert stored.error == "Research job store failed."


def test_run_research_job_keeps_failed_state_when_terminal_store_write_fails(
    monkeypatch,
    tmp_path,
) -> None:
    persist_calls = 0

    def fail_second_persist() -> None:
        nonlocal persist_calls
        persist_calls += 1
        if persist_calls == 2:
            raise jobs_module.ResearchJobsStoreError("secret path")

    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider payload")

    store_path = tmp_path / "jobs.json"
    job = jobs_module.ResearchJob(
        id="job-terminal-failure",
        query="Fail terminal persist",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    jobs_module.reset_research_jobs_state(store_path=store_path, jobs=[job])
    monkeypatch.setattr(jobs_module, "_persist_research_jobs_locked", fail_second_persist)
    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence("2026-04-27T20:00:01Z", "2026-04-27T20:00:02Z"),
    )

    api_module._run_research_job(job.id)

    assert persist_calls == 2
    stored = require_research_job_record(job.id)
    assert stored.status == "failed"
    assert stored.started_at == "2026-04-27T20:00:01Z"
    assert stored.finished_at == "2026-04-27T20:00:02Z"
    assert stored.error == "Research workflow failed."


def test_run_research_job_keeps_success_state_when_terminal_store_write_fails(
    monkeypatch,
    tmp_path,
) -> None:
    persist_calls = 0

    def fail_second_persist() -> None:
        nonlocal persist_calls
        persist_calls += 1
        if persist_calls == 2:
            raise jobs_module.ResearchJobsStoreError("secret path")

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    store_path = tmp_path / "jobs.json"
    job = jobs_module.ResearchJob(
        id="job-terminal-success",
        query="Succeed terminal persist",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    jobs_module.reset_research_jobs_state(store_path=store_path, jobs=[job])
    monkeypatch.setattr(jobs_module, "_persist_research_jobs_locked", fail_second_persist)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence("2026-04-27T20:00:01Z", "2026-04-27T20:00:02Z"),
    )

    api_module._run_research_job(job.id)

    assert persist_calls == 2
    stored = require_research_job_record(job.id)
    assert stored.status == "succeeded"
    assert stored.started_at == "2026-04-27T20:00:01Z"
    assert stored.finished_at == "2026-04-27T20:00:02Z"
    assert stored.result is not None
    assert stored.result["user_request"] == "Succeed terminal persist"


def test_run_research_job_skips_cancelled_job_without_store_write(
    monkeypatch,
    tmp_path,
) -> None:
    def fail_persist() -> None:
        raise AssertionError("persist should not be called")

    def fail_if_called(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    store_path = tmp_path / "jobs.json"
    job = jobs_module.ResearchJob(
        id="job-cancelled-before-worker",
        query="Cancelled",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
        status="cancelled",
        finished_at="2026-04-27T20:00:01Z",
    )
    jobs_module.reset_research_jobs_state(store_path=store_path, jobs=[job])
    monkeypatch.setattr(jobs_module, "_persist_research_jobs_locked", fail_persist)
    monkeypatch.setattr(api_module, "run_research", fail_if_called)

    api_module._run_research_job(job.id)

    stored = require_research_job_record(job.id)
    assert stored.status == "cancelled"
    assert stored.started_at is None
    assert stored.finished_at == "2026-04-27T20:00:01Z"


def test_run_research_job_updates_configured_store(monkeypatch, tmp_path) -> None:
    store_path = tmp_path / "jobs.json"

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    jobs_module.reset_research_jobs_state(store_path=store_path)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    job_id = client.post("/research/jobs", json={"query": "Persist result"}).json()[
        "job_id"
    ]

    payload = store_path.read_text(encoding="utf-8")
    assert f'"id": "{job_id}"' in payload
    assert '"status": "succeeded"' in payload
    assert '"report_markdown"' in payload


def test_cancel_research_job_updates_configured_store(monkeypatch, tmp_path) -> None:
    store_path = tmp_path / "jobs.json"
    fake_executor = FakeExecutor()
    jobs_module.reset_research_jobs_state(store_path=store_path)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    client = TestClient(api_module.app)

    job_id = client.post("/research/jobs", json={"query": "Cancel"}).json()["job_id"]
    response = client.post(f"/research/jobs/{job_id}/cancel")

    assert response.status_code == 200
    payload = store_path.read_text(encoding="utf-8")
    assert '"status": "cancelled"' in payload


def test_pruned_research_jobs_are_removed_from_configured_store(
    monkeypatch,
    tmp_path,
) -> None:
    store_path = tmp_path / "jobs.json"

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    jobs_module.reset_research_jobs_state(store_path=store_path, retained_limit=1)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    first = client.post("/research/jobs", json={"query": "First"}).json()["job_id"]
    second = client.post("/research/jobs", json={"query": "Second"}).json()["job_id"]

    payload = store_path.read_text(encoding="utf-8")
    assert first not in payload
    assert second in payload


def test_get_research_jobs_summary_returns_counts_and_active_jobs(monkeypatch) -> None:
    fake_executor = FakeExecutor()

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence(
            "2026-04-27T16:00:00Z",
            "2026-04-27T16:00:01Z",
            "2026-04-27T16:00:02Z",
            "2026-04-27T16:00:03Z",
            "2026-04-27T16:00:05Z",
            "2026-04-27T16:00:06Z",
            "2026-04-27T16:00:07Z",
            "2026-04-27T16:00:08Z",
            "2026-04-27T16:00:09Z",
            "2026-04-27T16:00:10Z",
        ),
    )
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    cancelled = client.post("/research/jobs", json={"query": "Cancelled"}).json()[
        "job_id"
    ]
    assert client.post(f"/research/jobs/{cancelled}/cancel").status_code == 200
    queued = client.post("/research/jobs", json={"query": "Queued"}).json()["job_id"]
    running = client.post("/research/jobs", json={"query": "Running"}).json()["job_id"]
    jobs_module.update_research_job_record(
        running,
        status="running",
        started_at="2026-04-27T16:00:04Z",
    )

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    client.post("/research/jobs", json={"query": "Succeeded"})

    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider payload")

    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    client.post("/research/jobs", json={"query": "Failed"})

    response = client.get("/research/jobs/summary")

    assert response.status_code == 200
    assert response.json() == {
        "counts": {
            "total": 5,
            "queued": 1,
            "running": 1,
            "succeeded": 1,
            "failed": 1,
            "cancelled": 1,
        },
        "active_count": 2,
        "active_limit": 100,
        "queued_jobs": [
            {
                "job_id": queued,
                "status": "queued",
                "query": "Queued",
                "preset": "offline",
                "created_at": "2026-04-27T16:00:02Z",
                "queue_position": 1,
            }
        ],
        "running_jobs": [
            {
                "job_id": running,
                "status": "running",
                "query": "Running",
                "preset": "offline",
                "created_at": "2026-04-27T16:00:03Z",
                "started_at": "2026-04-27T16:00:04Z",
            }
        ],
    }
    assert "secret provider payload" not in response.text
    assert "result" not in response.text
    assert "error" not in response.text


def test_get_research_jobs_summary_returns_empty_counts() -> None:
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    response = client.get("/research/jobs/summary")

    assert response.status_code == 200
    assert response.json() == {
        "counts": {
            "total": 0,
            "queued": 0,
            "running": 0,
            "succeeded": 0,
            "failed": 0,
            "cancelled": 0,
        },
        "active_count": 0,
        "active_limit": 100,
        "queued_jobs": [],
        "running_jobs": [],
    }


def test_get_research_jobs_summary_route_is_not_job_detail() -> None:
    jobs_module.reset_research_jobs_state()
    client = TestClient(api_module.app)

    response = client.get("/research/jobs/summary")

    assert response.status_code == 200
    assert response.json()["counts"]["total"] == 0


def test_create_research_job_prunes_oldest_finished_jobs(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    jobs_module.reset_research_jobs_state(retained_limit=2)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    first = client.post("/research/jobs", json={"query": "First"}).json()["job_id"]
    second = client.post("/research/jobs", json={"query": "Second"}).json()["job_id"]
    third = client.post("/research/jobs", json={"query": "Third"}).json()["job_id"]

    assert client.get(f"/research/jobs/{first}").status_code == 404
    assert client.get(f"/research/jobs/{second}").json()["status"] == "succeeded"
    assert client.get(f"/research/jobs/{third}").json()["status"] == "succeeded"


def test_create_research_job_does_not_prune_queued_or_running_jobs(monkeypatch) -> None:
    fake_executor = FakeExecutor()

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    jobs_module.reset_research_jobs_state(retained_limit=1)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    queued = client.post("/research/jobs", json={"query": "Queued"}).json()["job_id"]
    running = client.post("/research/jobs", json={"query": "Running"}).json()["job_id"]
    jobs_module.update_research_job_record(running, status="running")

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    finished = client.post("/research/jobs", json={"query": "Finished"}).json()["job_id"]
    newest = client.post("/research/jobs", json={"query": "Newest"}).json()["job_id"]

    assert client.get(f"/research/jobs/{queued}").json()["status"] == "queued"
    assert client.get(f"/research/jobs/{running}").json()["status"] == "running"
    assert client.get(f"/research/jobs/{finished}").status_code == 404
    assert client.get(f"/research/jobs/{newest}").json()["status"] == "succeeded"


def test_create_research_job_prunes_oldest_failed_jobs(monkeypatch) -> None:
    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("provider failed")

    jobs_module.reset_research_jobs_state(retained_limit=1)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence(
            "2026-04-27T14:00:00Z",
            "2026-04-27T14:00:01Z",
            "2026-04-27T14:00:02Z",
            "2026-04-27T14:00:03Z",
            "2026-04-27T14:00:04Z",
            "2026-04-27T14:00:05Z",
        ),
    )
    client = TestClient(api_module.app)

    first = client.post("/research/jobs", json={"query": "First"}).json()["job_id"]
    second = client.post("/research/jobs", json={"query": "Second"}).json()["job_id"]

    assert client.get(f"/research/jobs/{first}").status_code == 404
    assert without_progress_fields(client.get(f"/research/jobs/{second}").json()) == {
        "job_id": second,
        "status": "failed",
        "created_at": "2026-04-27T14:00:03Z",
        "started_at": "2026-04-27T14:00:04Z",
        "finished_at": "2026-04-27T14:00:05Z",
        "error": "Research workflow failed.",
    }


def test_create_research_job_prunes_oldest_cancelled_jobs(monkeypatch) -> None:
    fake_executor = FakeExecutor()
    jobs_module.reset_research_jobs_state(retained_limit=1)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence(
            "2026-04-27T15:00:00Z",
            "2026-04-27T15:00:01Z",
            "2026-04-27T15:00:02Z",
            "2026-04-27T15:00:03Z",
        ),
    )
    client = TestClient(api_module.app)

    first = client.post("/research/jobs", json={"query": "First"}).json()["job_id"]
    assert client.post(f"/research/jobs/{first}/cancel").status_code == 200
    second = client.post("/research/jobs", json={"query": "Second"}).json()["job_id"]
    assert client.post(f"/research/jobs/{second}/cancel").status_code == 200

    assert client.get(f"/research/jobs/{first}").status_code == 404
    assert without_progress_fields(client.get(f"/research/jobs/{second}").json()) == {
        "job_id": second,
        "status": "cancelled",
        "created_at": "2026-04-27T15:00:02Z",
        "finished_at": "2026-04-27T15:00:03Z",
    }
