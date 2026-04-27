import os

from fastapi.testclient import TestClient

import insight_graph.api as api_module
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


def test_health_returns_ok() -> None:
    client = TestClient(api_module.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    response = client.post("/research/jobs", json={"query": "Compare Cursor"})

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert isinstance(payload["job_id"], str)
    assert len(fake_executor.submissions) == 1


def test_create_research_job_response_stays_queued_if_executor_runs_immediately(
    monkeypatch,
) -> None:
    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    response = client.post("/research/jobs", json={"query": "Compare Cursor"})

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    job_response = client.get(f"/research/jobs/{payload['job_id']}")
    assert job_response.json()["status"] == "succeeded"


def test_get_research_job_returns_success_result(monkeypatch) -> None:
    fake_executor = FakeExecutor()
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    create_response = client.post("/research/jobs", json={"query": "  Compare Cursor  "})
    job_id = create_response.json()["job_id"]

    queued_response = client.get(f"/research/jobs/{job_id}")
    assert queued_response.status_code == 200
    assert queued_response.json() == {"job_id": job_id, "status": "queued"}

    fake_executor.run_next()

    response = client.get(f"/research/jobs/{job_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["status"] == "succeeded"
    assert payload["result"]["user_request"] == "Compare Cursor"
    assert payload["result"]["competitive_matrix"][0]["product"] == "Cursor"
    assert observed_queries == ["Compare Cursor"]


def test_get_research_job_returns_safe_failure(monkeypatch) -> None:
    fake_executor = FakeExecutor()

    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider payload")

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    create_response = client.post("/research/jobs", json={"query": "Compare Cursor"})
    job_id = create_response.json()["job_id"]
    fake_executor.run_next()

    response = client.get(f"/research/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": job_id,
        "status": "failed",
        "error": "Research workflow failed.",
    }
    assert "secret provider payload" not in response.text


def test_get_research_job_returns_404_for_unknown_job() -> None:
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    response = client.get("/research/jobs/missing")

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
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    job_id = client.post("/research/jobs", json={"query": "Cancel me"}).json()[
        "job_id"
    ]

    response = client.post(f"/research/jobs/{job_id}/cancel")

    assert response.status_code == 200
    assert response.json() == {"job_id": job_id, "status": "cancelled"}
    assert client.get(f"/research/jobs/{job_id}").json() == {
        "job_id": job_id,
        "status": "cancelled",
    }

    fake_executor.run_next()

    assert observed_queries == []
    assert client.get(f"/research/jobs/{job_id}").json()["status"] == "cancelled"


def test_cancel_research_job_returns_404_for_unknown_job() -> None:
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    response = client.post("/research/jobs/missing/cancel")

    assert response.status_code == 404
    assert response.json() == {"detail": "Research job not found."}


def test_cancel_research_job_rejects_running_or_finished_jobs(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    job_id = client.post("/research/jobs", json={"query": "Finished"}).json()[
        "job_id"
    ]

    with api_module._JOBS_LOCK:
        api_module._JOBS[job_id].status = "running"
    running_response = client.post(f"/research/jobs/{job_id}/cancel")
    assert running_response.status_code == 409
    assert running_response.json() == {
        "detail": "Only queued research jobs can be cancelled."
    }

    with api_module._JOBS_LOCK:
        api_module._JOBS[job_id].status = "succeeded"
    succeeded_response = client.post(f"/research/jobs/{job_id}/cancel")
    assert succeeded_response.status_code == 409
    assert succeeded_response.json() == {
        "detail": "Only queued research jobs can be cancelled."
    }

    with api_module._JOBS_LOCK:
        api_module._JOBS[job_id].status = "failed"
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
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    cancelled = client.post("/research/jobs", json={"query": "Cancelled"}).json()[
        "job_id"
    ]
    cancel_response = client.post(f"/research/jobs/{cancelled}/cancel")
    assert cancel_response.status_code == 200

    queued = client.post("/research/jobs", json={"query": "Queued"}).json()["job_id"]
    running = client.post("/research/jobs", json={"query": "Running"}).json()["job_id"]
    with api_module._JOBS_LOCK:
        api_module._JOBS[running].status = "running"

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
            },
            {
                "job_id": succeeded,
                "status": "succeeded",
                "query": "Succeeded",
                "preset": "offline",
            },
            {
                "job_id": running,
                "status": "running",
                "query": "Running",
                "preset": "offline",
            },
            {
                "job_id": queued,
                "status": "queued",
                "query": "Queued",
                "preset": "offline",
            },
            {
                "job_id": cancelled,
                "status": "cancelled",
                "query": "Cancelled",
                "preset": "offline",
            },
        ],
        "count": 5,
    }
    assert "secret provider payload" not in response.text
    assert "result" not in response.text
    assert "error" not in response.text


def test_create_research_job_prunes_oldest_finished_jobs(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_MAX_RESEARCH_JOBS", 2)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    api_module._JOBS.clear()
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

    monkeypatch.setattr(api_module, "_MAX_RESEARCH_JOBS", 1)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    queued = client.post("/research/jobs", json={"query": "Queued"}).json()["job_id"]
    running = client.post("/research/jobs", json={"query": "Running"}).json()["job_id"]
    with api_module._JOBS_LOCK:
        api_module._JOBS[running].status = "running"

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

    monkeypatch.setattr(api_module, "_MAX_RESEARCH_JOBS", 1)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    first = client.post("/research/jobs", json={"query": "First"}).json()["job_id"]
    second = client.post("/research/jobs", json={"query": "Second"}).json()["job_id"]

    assert client.get(f"/research/jobs/{first}").status_code == 404
    assert client.get(f"/research/jobs/{second}").json() == {
        "job_id": second,
        "status": "failed",
        "error": "Research workflow failed.",
    }


def test_create_research_job_prunes_oldest_cancelled_jobs(monkeypatch) -> None:
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_MAX_RESEARCH_JOBS", 1)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    first = client.post("/research/jobs", json={"query": "First"}).json()["job_id"]
    assert client.post(f"/research/jobs/{first}/cancel").status_code == 200
    second = client.post("/research/jobs", json={"query": "Second"}).json()["job_id"]
    assert client.post(f"/research/jobs/{second}/cancel").status_code == 200

    assert client.get(f"/research/jobs/{first}").status_code == 404
    assert client.get(f"/research/jobs/{second}").json() == {
        "job_id": second,
        "status": "cancelled",
    }
