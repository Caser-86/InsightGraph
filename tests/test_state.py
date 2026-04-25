from insight_graph import __version__
from insight_graph.cli import app
from insight_graph.llm.observability import build_llm_call_record
from insight_graph.state import Evidence, GraphState, LLMCallRecord, Subtask, ToolCallRecord


def test_package_version_is_defined() -> None:
    assert __version__ == "0.1.0"


def test_cli_app_is_importable() -> None:
    assert app.info.help == "InsightGraph research workflow CLI"


def test_subtask_defaults_to_research_type() -> None:
    subtask = Subtask(id="s1", description="Compare Cursor and GitHub Copilot")

    assert subtask.subtask_type == "research"
    assert subtask.dependencies == []
    assert subtask.suggested_tools == []


def test_evidence_requires_source_url() -> None:
    evidence = Evidence(
        id="e1",
        subtask_id="s1",
        title="Cursor pricing",
        source_url="https://cursor.com/pricing",
        snippet="Cursor publishes pricing tiers on its pricing page.",
        source_type="official_site",
    )

    assert evidence.verified is False
    assert evidence.source_domain == "cursor.com"


def test_graph_state_starts_with_empty_collections() -> None:
    state = GraphState(user_request="Analyze AI coding agents")

    assert state.user_request == "Analyze AI coding agents"
    assert state.subtasks == []
    assert state.evidence_pool == []
    assert state.findings == []
    assert state.report_markdown is None


def test_tool_call_record_defaults_to_success() -> None:
    record = ToolCallRecord(
        subtask_id="collect",
        tool_name="mock_search",
        query="Compare AI coding agents",
    )

    assert record.evidence_count == 0
    assert record.filtered_count == 0
    assert record.success is True
    assert record.error is None


def test_graph_state_starts_with_executor_collections() -> None:
    state = GraphState(user_request="Analyze AI coding agents")

    assert state.global_evidence_pool == []
    assert state.tool_call_log == []


def test_llm_call_record_stores_metadata_only() -> None:
    record = LLMCallRecord(
        stage="analyst",
        provider="llm",
        model="relay-model",
        success=True,
        duration_ms=12,
    )

    assert record.stage == "analyst"
    assert record.provider == "llm"
    assert record.model == "relay-model"
    assert record.success is True
    assert record.duration_ms == 12
    assert record.error is None


def test_graph_state_starts_with_empty_llm_call_log() -> None:
    state = GraphState(user_request="Analyze AI coding agents")

    assert state.llm_call_log == []


def test_build_llm_call_record_sanitizes_secret_values() -> None:
    record = build_llm_call_record(
        stage="reporter",
        provider="llm",
        model="relay-model",
        success=False,
        duration_ms=3,
        error=RuntimeError("request failed for sk-secret-value"),
        secrets=["sk-secret-value"],
    )

    assert record.error == "RuntimeError: request failed for [REDACTED]"
    assert "sk-secret-value" not in record.model_dump_json()
