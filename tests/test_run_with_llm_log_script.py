from datetime import UTC, datetime

import scripts.run_with_llm_log as llm_log_script
from insight_graph.state import (
    CompetitiveMatrixRow,
    Critique,
    Finding,
    GraphState,
    LLMCallRecord,
    ToolCallRecord,
)

FIXED_NOW = datetime(2026, 4, 26, 12, 0, tzinfo=UTC)


def make_state(query: str) -> GraphState:
    return GraphState(
        user_request=query,
        report_markdown="# InsightGraph Research Report\n\n## References\n",
        findings=[
            Finding(
                title="Sensitive finding title should not be logged",
                summary="Sensitive finding summary should not be logged",
                evidence_ids=["evidence-1"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Cursor",
                positioning="Sensitive matrix positioning should not be logged",
                strengths=["Sensitive matrix strength should not be logged"],
                evidence_ids=["evidence-1"],
            )
        ],
        critique=Critique(passed=True, reason="Citations present."),
        tool_call_log=[
            ToolCallRecord(
                subtask_id="collect",
                tool_name="mock_search",
                query=query,
                evidence_count=3,
                filtered_count=0,
                success=True,
            )
        ],
        llm_call_log=[
            LLMCallRecord(
                stage="reporter",
                provider="llm",
                model="relay-model",
                wire_api="responses",
                success=True,
                duration_ms=12,
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
            )
        ],
        iterations=2,
    )


def test_build_log_payload_contains_only_safe_metadata():
    state = make_state("Compare Cursor")

    payload = llm_log_script.build_log_payload(state, preset="offline")

    assert payload == {
        "query": "Compare Cursor",
        "preset": "offline",
        "report_markdown_length": len(state.report_markdown or ""),
        "finding_count": 1,
        "competitive_matrix_row_count": 1,
        "tool_call_log": [state.tool_call_log[0].model_dump(mode="json")],
        "llm_call_log": [state.llm_call_log[0].model_dump(mode="json")],
        "iterations": 2,
    }


def test_build_log_payload_omits_sensitive_fields():
    state = make_state("Compare Cursor")
    payload = llm_log_script.build_log_payload(state, preset="offline")

    payload_text = str(payload).lower()

    assert "report_markdown" not in payload
    assert "# insightgraph research report" not in payload_text
    assert "sensitive finding" not in payload_text
    assert "sensitive matrix" not in payload_text
    assert "evidence_pool" not in payload_text
    assert "prompt" not in payload_text
    assert "completion" not in payload_text
    assert "api_key" not in payload_text


def test_slugify_query_limits_and_normalizes_filename_component():
    slug = llm_log_script.slugify_query("  Cursor + OpenCode / GitHub Copilot!!!  ")

    assert slug == "cursor-opencode-github-copilot"
    assert len(llm_log_script.slugify_query("a" * 200)) == 60
    assert llm_log_script.slugify_query("!!!") == "research"


def test_build_log_path_uses_utc_timestamp_slug_and_collision_suffix(tmp_path):
    first = llm_log_script.build_log_path(
        log_dir=tmp_path,
        query="Compare Cursor, OpenCode, and GitHub Copilot",
        now=FIXED_NOW,
    )
    first.write_text("existing", encoding="utf-8")
    second = llm_log_script.build_log_path(
        log_dir=tmp_path,
        query="Compare Cursor, OpenCode, and GitHub Copilot",
        now=FIXED_NOW,
    )

    assert first.name == "20260426T120000Z-compare-cursor-opencode-and-github-copilot.json"
    assert second.name == "20260426T120000Z-compare-cursor-opencode-and-github-copilot-2.json"
