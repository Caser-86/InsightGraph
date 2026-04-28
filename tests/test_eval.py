import json

import insight_graph.eval as eval_module
from insight_graph.state import (
    CompetitiveMatrixRow,
    Critique,
    Evidence,
    Finding,
    GraphState,
    ToolCallRecord,
)


def make_eval_state(query: str) -> GraphState:
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


def test_build_eval_payload_scores_case_rules(monkeypatch) -> None:
    monkeypatch.setattr(eval_module.time, "perf_counter", iter([1.0, 1.025]).__next__)

    payload = eval_module.build_eval_payload(
        [eval_module.EvalCase(query="Compare Cursor", min_references=2)],
        run_research_func=make_eval_state,
    )

    case = payload["cases"][0]
    assert case["score"] == 100
    assert case["passed"] is True
    assert case["duration_ms"] == 25
    assert {rule["id"] for rule in case["rules"]} == {
        "critique_passed",
        "has_report",
        "has_competitive_matrix_section",
        "references_meet_minimum",
        "findings_meet_minimum",
        "matrix_rows_meet_minimum",
        "findings_cite_evidence",
        "matrix_rows_cite_evidence",
    }
    assert all(rule["passed"] for rule in case["rules"])
    assert payload["summary"]["average_score"] == 100
    assert payload["summary"]["passed_count"] == 1
    assert payload["summary"]["failed_count"] == 0


def test_build_eval_payload_records_failed_rules() -> None:
    def weak_state(query: str) -> GraphState:
        state = make_eval_state(query)
        state.findings = []
        state.competitive_matrix = []
        state.report_markdown = "# Report\n\n## References\n\n[1] Only one. https://example.com\n"
        return state

    payload = eval_module.build_eval_payload(
        [eval_module.EvalCase(query="Weak", min_references=2)],
        run_research_func=weak_state,
    )

    case = payload["cases"][0]
    assert case["score"] < 80
    assert case["passed"] is False
    assert payload["summary"]["failed_count"] == 1
    assert payload["summary"]["failed_rules"]["findings_meet_minimum"] == 1
    assert payload["summary"]["failed_rules"]["matrix_rows_meet_minimum"] == 1


def test_format_markdown_includes_eval_score_columns() -> None:
    payload = {
        "cases": [
            {
                "query": "Compare Cursor",
                "duration_ms": 25,
                "score": 100,
                "passed": True,
                "finding_count": 1,
                "competitive_matrix_row_count": 1,
                "reference_count": 2,
                "tool_call_count": 1,
                "llm_call_count": 0,
                "critique_passed": True,
                "report_has_competitive_matrix": True,
                "rules": [],
            }
        ],
        "summary": {
            "case_count": 1,
            "average_score": 100,
            "passed_count": 1,
            "failed_count": 0,
            "failed_rules": {},
            "total_duration_ms": 25,
            "all_critique_passed": True,
            "total_findings": 1,
            "total_competitive_matrix_rows": 1,
            "total_references": 2,
            "total_tool_calls": 1,
            "total_llm_calls": 0,
        },
    }

    markdown = eval_module.format_markdown(payload)

    assert markdown.startswith("# InsightGraph Eval Bench\n")
    assert "| Query | Score | Passed | Duration ms |" in markdown
    assert "| Compare Cursor | 100 | true | 25 |" in markdown
    assert "| Cases | Average score | Passed | Failed |" in markdown


def test_main_writes_json_output_file(monkeypatch, tmp_path, capsys) -> None:
    payload = {
        "cases": [],
        "summary": {
            "case_count": 0,
            "average_score": 0,
            "passed_count": 0,
            "failed_count": 0,
            "failed_rules": {},
            "total_duration_ms": 0,
            "all_critique_passed": True,
            "total_findings": 0,
            "total_competitive_matrix_rows": 0,
            "total_references": 0,
            "total_tool_calls": 0,
            "total_llm_calls": 0,
        },
    }
    output_path = tmp_path / "eval.json"
    monkeypatch.setattr(eval_module, "build_eval_payload", lambda: payload)

    exit_code = eval_module.main(["--output", str(output_path)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_pyproject_registers_eval_console_script() -> None:
    pyproject = (eval_module.Path(__file__).parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )

    assert 'insight-graph-eval = "insight_graph.eval:main"' in pyproject
