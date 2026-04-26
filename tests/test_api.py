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
