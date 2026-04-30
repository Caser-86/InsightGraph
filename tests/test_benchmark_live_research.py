import json
import os
from pathlib import Path

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
                section_id="executive-summary",
            ),
            Evidence(
                id="source-2",
                subtask_id="collect",
                title="Docs Source",
                source_url="https://docs.example.com/source",
                snippet="Documentation evidence.",
                source_type="docs",
                verified=True,
                reachable=False,
                section_id="references",
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
        [
            "--allow-live",
            "--output",
            str(output),
            "--case",
            "Compare Cursor",
            "--expected-section",
            "References",
        ],
        run_research_func=fake_run_research,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert observed_queries == ["Compare Cursor"]
    assert payload["preset"] == "live-research"
    assert payload["cases"][0]["url_validity_count"] == 1
    assert payload["cases"][0]["url_validation_rate"] == 50
    assert payload["cases"][0]["citation_precision_proxy"] == 100
    assert payload["cases"][0]["source_diversity_count"] == 2
    assert payload["cases"][0]["source_diversity_by_type"] == {
        "docs": 1,
        "official_site": 1,
    }
    assert payload["cases"][0]["source_diversity_by_domain"] == {
        "docs.example.com": 1,
        "example.com": 1,
    }
    assert payload["cases"][0]["report_depth_words"] > 0
    assert payload["cases"][0]["section_coverage"] == 100
    assert payload["cases"][0]["expected_sections_present"] == ["References"]
    assert payload["cases"][0]["expected_sections_missing"] == []
    assert payload["cases"][0]["llm_call_count"] == 1
    assert payload["cases"][0]["tool_call_count"] == 1
    assert payload["cases"][0]["total_tokens"] == 42
    assert payload["summary"]["total_tool_calls"] == 1
    assert payload["summary"]["average_url_validation_rate"] == 50
    assert payload["summary"]["average_citation_precision_proxy"] == 100
    assert payload["summary"]["average_report_depth_words"] > 0
    assert payload["summary"]["average_section_coverage"] == 100
    assert not os.getenv("INSIGHT_GRAPH_USE_WEB_SEARCH")


def test_live_benchmark_case_profiles_define_quality_targets() -> None:
    case_path = Path("docs/benchmarks/live-research-cases.json")

    payload = json.loads(case_path.read_text(encoding="utf-8"))

    case_ids = {case["id"] for case in payload["cases"]}
    assert case_ids == {
        "ai-coding-agents",
        "public-company-analysis",
        "sec-filing-risk-analysis",
        "technology-trend-analysis",
    }
    for case in payload["cases"]:
        assert case["query"]
        assert case["expected_sections"]
        assert case["required_source_types"]
        assert case["minimum_source_diversity"] >= 2
        assert case["report_depth_target_words"] >= 500


def test_live_benchmark_loads_case_profiles_from_file(tmp_path, monkeypatch) -> None:
    case_file = tmp_path / "cases.json"
    case_file.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "custom-case",
                        "query": "Compare Cursor and Copilot",
                        "expected_sections": ["Executive Summary", "References"],
                        "required_source_types": ["official_site", "docs"],
                        "minimum_source_diversity": 2,
                        "report_depth_target_words": 700,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "live.json"
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_live_state(query)

    exit_code = benchmark_module.main(
        ["--allow-live", "--output", str(output), "--case-file", str(case_file)],
        run_research_func=fake_run_research,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert observed_queries == ["Compare Cursor and Copilot"]
    assert payload["cases"][0]["case_id"] == "custom-case"
    assert payload["cases"][0]["expected_sections"] == ["Executive Summary", "References"]
    assert payload["cases"][0]["required_source_types"] == ["official_site", "docs"]
    assert payload["cases"][0]["minimum_source_diversity"] == 2
    assert payload["cases"][0]["report_depth_target_words"] == 700
