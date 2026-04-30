import json
import os

from insight_graph.state import (
    Critique,
    Evidence,
    Finding,
    GraphState,
    LLMCallRecord,
    ToolCallRecord,
)
from scripts import benchmark_live_research as benchmark_module


def make_live_state(query: str) -> GraphState:
    return GraphState(
        user_request=query,
        evidence_pool=[
            Evidence(
                id="source-1",
                subtask_id="collect",
                title="Official Source",
                source_url="https://example.com/source",
                snippet="Official evidence.",
                source_type="official_site",
                verified=True,
                reachable=True,
            )
        ],
        findings=[
            Finding(
                title="Finding",
                summary="Supported finding.",
                evidence_ids=["source-1"],
            )
        ],
        critique=Critique(passed=True, reason="Supported."),
        tool_call_log=[ToolCallRecord(subtask_id="collect", tool_name="web_search", query=query)],
        llm_call_log=[
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="model",
                success=True,
                duration_ms=10,
                total_tokens=42,
            )
        ],
        citation_support=[{"support_status": "supported", "claim": "Supported finding."}],
        report_markdown=(
            "# InsightGraph Research Report\n\n"
            "## Key Findings\n\nSupported finding. [1]\n\n"
            "## References\n\n[1] Official Source. https://example.com/source\n"
        ),
    )


def test_live_benchmark_requires_explicit_opt_in(tmp_path) -> None:
    output = tmp_path / "live.json"

    exit_code = benchmark_module.main(["--output", str(output)])

    assert exit_code == 2
    assert not output.exists()


def test_live_benchmark_writes_metrics_artifact_with_fake_research(tmp_path, monkeypatch) -> None:
    output = tmp_path / "live.json"
    observed_queries: list[str] = []
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_live_state(query)

    exit_code = benchmark_module.main(
        ["--allow-live", "--output", str(output), "--case", "Compare Cursor"],
        run_research_func=fake_run_research,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert observed_queries == ["Compare Cursor"]
    assert payload["preset"] == "live-research"
    assert payload["cases"][0]["url_validity_count"] == 1
    assert payload["cases"][0]["citation_precision_proxy"] == 100
    assert payload["cases"][0]["source_diversity_count"] == 1
    assert payload["cases"][0]["report_depth_words"] > 0
    assert payload["cases"][0]["llm_call_count"] == 1
    assert payload["cases"][0]["total_tokens"] == 42
    assert not os.getenv("INSIGHT_GRAPH_USE_WEB_SEARCH")
