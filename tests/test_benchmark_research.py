import os

import scripts.benchmark_research as benchmark_module
from insight_graph.state import (
    CompetitiveMatrixRow,
    Critique,
    Evidence,
    Finding,
    GraphState,
    ToolCallRecord,
)


def make_benchmark_state(query: str) -> GraphState:
    return GraphState(
        user_request=query,
        evidence_pool=[
            Evidence(
                id="cursor-pricing",
                subtask_id="collect",
                title="Cursor Pricing",
                source_url="https://cursor.com/pricing",
                snippet="Cursor pricing evidence.",
                source_type="official_site",
                verified=True,
            ),
            Evidence(
                id="copilot-docs",
                subtask_id="collect",
                title="GitHub Copilot Documentation",
                source_url="https://docs.github.com/en/copilot",
                snippet="Copilot documentation evidence.",
                source_type="docs",
                verified=True,
            ),
        ],
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
                evidence_count=2,
            )
        ],
        report_markdown=(
            "# InsightGraph Research Report\n\n"
            "## Key Findings\n\n"
            "Packaging differs. [1]\n\n"
            "## Competitive Matrix\n\n"
            "| Product | Positioning | Strengths | Evidence |\n"
            "| --- | --- | --- | --- |\n"
            "| Cursor | Official product positioning signal | "
            "Official/documented source coverage | [1] |\n\n"
            "## References\n\n"
            "[1] Cursor Pricing. https://cursor.com/pricing\n"
            "[2] GitHub Copilot Documentation. https://docs.github.com/en/copilot\n"
        ),
    )


def test_build_benchmark_payload_contains_case_metrics(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return make_benchmark_state(query)

    monkeypatch.setattr(benchmark_module.time, "perf_counter", iter([1.0, 1.025]).__next__)

    payload = benchmark_module.build_benchmark_payload(
        ["Compare Cursor and GitHub Copilot"],
        run_research_func=fake_run_research,
    )

    assert payload["cases"] == [
        {
            "query": "Compare Cursor and GitHub Copilot",
            "duration_ms": 25,
            "finding_count": 1,
            "competitive_matrix_row_count": 1,
            "reference_count": 2,
            "tool_call_count": 1,
            "llm_call_count": 0,
            "critique_passed": True,
            "report_has_competitive_matrix": True,
        }
    ]
    assert payload["summary"] == {
        "case_count": 1,
        "total_duration_ms": 25,
        "all_critique_passed": True,
        "total_findings": 1,
        "total_competitive_matrix_rows": 1,
        "total_references": 2,
        "total_tool_calls": 1,
        "total_llm_calls": 0,
    }


def test_benchmark_clears_runtime_opt_in_env_for_case(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env["INSIGHT_GRAPH_USE_WEB_SEARCH"] = os.getenv("INSIGHT_GRAPH_USE_WEB_SEARCH")
        observed_env["INSIGHT_GRAPH_ANALYST_PROVIDER"] = os.getenv("INSIGHT_GRAPH_ANALYST_PROVIDER")
        return make_benchmark_state(query)

    benchmark_module.build_benchmark_payload(
        ["Compare Cursor and GitHub Copilot"],
        run_research_func=fake_run_research,
    )

    assert observed_env == {
        "INSIGHT_GRAPH_USE_WEB_SEARCH": None,
        "INSIGHT_GRAPH_ANALYST_PROVIDER": None,
    }
    assert os.getenv("INSIGHT_GRAPH_USE_WEB_SEARCH") == "1"
    assert os.getenv("INSIGHT_GRAPH_ANALYST_PROVIDER") == "llm"
