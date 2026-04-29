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
                section_id="pricing-and-packaging",
            ),
            Evidence(
                id="copilot-docs",
                subtask_id="collect",
                title="GitHub Copilot Documentation",
                source_url="https://docs.github.com/en/copilot",
                snippet="Copilot documentation evidence.",
                source_type="docs",
                verified=True,
                section_id="product-positioning",
            ),
        ],
        section_research_plan=[
            {"section_id": "pricing-and-packaging", "title": "Pricing and Packaging"},
            {"section_id": "product-positioning", "title": "Product Positioning"},
        ],
        section_collection_status=[
            {
                "section_id": "pricing-and-packaging",
                "required_source_types": ["official_site"],
                "covered_source_types": ["official_site"],
            },
            {
                "section_id": "product-positioning",
                "required_source_types": ["docs", "news"],
                "covered_source_types": ["docs"],
            },
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


def test_build_eval_payload_includes_report_quality_metrics(monkeypatch) -> None:
    monkeypatch.setattr(eval_module.time, "perf_counter", iter([1.0, 1.025]).__next__)

    payload = eval_module.build_eval_payload(
        [eval_module.EvalCase(query="Compare Cursor", min_references=2)],
        run_research_func=make_eval_state,
    )

    quality = payload["cases"][0]["quality"]
    assert quality["section_count"] == 3
    assert quality["required_sections_present"] == [
        "Key Findings",
        "Competitive Matrix",
        "References",
    ]
    assert quality["missing_required_sections"] == []
    assert quality["section_coverage_score"] == 100
    assert quality["report_word_count"] > 0
    assert 0 < quality["report_depth_score"] <= 100
    assert quality["unique_source_domain_count"] == 2
    assert quality["unique_source_type_count"] == 2
    assert quality["source_diversity_score"] == 67
    assert quality["verified_evidence_count"] == 2
    assert quality["evidence_per_section"] == {
        "pricing-and-packaging": 1,
        "product-positioning": 1,
    }
    assert quality["average_evidence_per_section"] == 1
    assert quality["official_source_coverage_score"] == 67
    assert quality["unsupported_finding_count"] == 0
    assert quality["unsupported_matrix_row_count"] == 0
    assert quality["unsupported_claim_count"] == 0
    assert quality["citation_support_score"] == 100
    assert quality["duplicate_source_rate"] == 0


def test_eval_summary_includes_report_quality_aggregates(monkeypatch) -> None:
    monkeypatch.setattr(eval_module.time, "perf_counter", iter([1.0, 1.025]).__next__)

    payload = eval_module.build_eval_payload(
        [eval_module.EvalCase(query="Compare Cursor", min_references=2)],
        run_research_func=make_eval_state,
    )

    summary = payload["summary"]
    assert summary["average_section_coverage_score"] == 100
    assert summary["average_report_depth_score"] == payload["cases"][0]["quality"][
        "report_depth_score"
    ]
    assert summary["average_source_diversity_score"] == 67
    assert summary["average_evidence_per_section"] == 1
    assert summary["average_official_source_coverage_score"] == 67
    assert summary["average_citation_support_score"] == 100
    assert summary["total_unsupported_claims"] == 0
    assert summary["average_duplicate_source_rate"] == 0


def test_report_quality_metrics_detect_unsupported_claims_and_missing_sections() -> None:
    state = GraphState(
        user_request="Weak report",
        evidence_pool=[
            Evidence(
                id="source-1",
                subtask_id="collect",
                title="Only Source",
                source_url="https://example.com/source",
                snippet="Only source evidence.",
                source_type="blog",
                verified=True,
            )
        ],
        findings=[
            Finding(
                title="Unsupported finding",
                summary="This finding points to missing evidence.",
                evidence_ids=["missing-evidence"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Example",
                positioning="No cited positioning.",
                strengths=[],
                evidence_ids=[],
            )
        ],
        critique=Critique(passed=False, reason="Weak evidence."),
        report_markdown="# Weak Report\n\n## Key Findings\n\nUnsupported claim. [1]\n",
    )

    quality = eval_module.build_report_quality_metrics(state, state.report_markdown or "")

    assert quality["missing_required_sections"] == ["Competitive Matrix", "References"]
    assert quality["section_coverage_score"] == 33
    assert quality["unsupported_finding_count"] == 1
    assert quality["unsupported_matrix_row_count"] == 1
    assert quality["unsupported_claim_count"] == 2
    assert quality["citation_support_score"] == 0


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
                "quality": {
                    "section_count": 3,
                    "required_sections_present": [
                        "Key Findings",
                        "Competitive Matrix",
                        "References",
                    ],
                    "missing_required_sections": [],
                    "section_coverage_score": 100,
                    "report_word_count": 42,
                    "report_depth_score": 17,
                    "unique_source_domain_count": 2,
                    "unique_source_type_count": 2,
                    "source_diversity_score": 67,
                    "verified_evidence_count": 2,
                    "evidence_per_section": {
                        "pricing-and-packaging": 1,
                        "product-positioning": 1,
                    },
                    "average_evidence_per_section": 1,
                    "official_source_coverage_score": 67,
                    "unsupported_finding_count": 0,
                    "unsupported_matrix_row_count": 0,
                    "unsupported_claim_count": 0,
                    "citation_support_score": 100,
                    "duplicate_source_rate": 0,
                },
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
            "average_section_coverage_score": 100,
            "average_report_depth_score": 17,
            "average_source_diversity_score": 67,
            "average_evidence_per_section": 1,
            "average_official_source_coverage_score": 67,
            "average_citation_support_score": 100,
            "total_unsupported_claims": 0,
            "average_duplicate_source_rate": 0,
        },
    }

    markdown = eval_module.format_markdown(payload)

    assert markdown.startswith("# InsightGraph Eval Bench\n")
    assert "| Query | Score | Passed | Duration ms |" in markdown
    assert "| Compare Cursor | 100 | true | 25 |" in markdown
    assert "| Cases | Average score | Passed | Failed |" in markdown
    assert "## Report Quality" in markdown
    assert (
        "| Query | Section coverage | Report depth | Source diversity | Citation support "
        "| Evidence/section | Official source coverage | Unsupported claims "
        "| Duplicate source rate |"
    ) in markdown
    assert "| Compare Cursor | 100 | 17 | 67 | 100 | 1 | 67 | 0 | 0 |" in markdown
    assert "## Report Quality Summary" in markdown
    assert (
        "| Avg section coverage | Avg report depth | Avg source diversity "
        "| Avg citation support | Avg evidence/section | Avg official source coverage "
        "| Unsupported claims | Avg duplicate source rate |"
    ) in markdown


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


def test_load_eval_cases_reads_case_file(tmp_path) -> None:
    case_file = tmp_path / "cases.json"
    case_file.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "query": "Compare Cursor",
                        "min_findings": 2,
                        "min_matrix_rows": 3,
                        "min_references": 4,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    cases = eval_module.load_eval_cases(case_file)

    assert cases == [
        eval_module.EvalCase(
            query="Compare Cursor",
            min_findings=2,
            min_matrix_rows=3,
            min_references=4,
        )
    ]


def test_main_uses_case_file(monkeypatch, tmp_path) -> None:
    observed_cases: list[eval_module.EvalCase] = []
    case_file = tmp_path / "cases.json"
    case_file.write_text(
        json.dumps({"cases": [{"query": "Compare Cursor", "min_references": 4}]}),
        encoding="utf-8",
    )

    def fake_build_eval_payload(cases=None, run_research_func=eval_module.run_research):
        observed_cases.extend(cases)
        return {
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

    monkeypatch.setattr(eval_module, "build_eval_payload", fake_build_eval_payload)

    exit_code = eval_module.main(["--case-file", str(case_file)])

    assert exit_code == 0
    assert observed_cases == [
        eval_module.EvalCase(query="Compare Cursor", min_references=4)
    ]


def test_main_returns_two_for_malformed_case_file(tmp_path, capsys) -> None:
    case_file = tmp_path / "cases.json"
    case_file.write_text(json.dumps({"cases": [{"query": ""}]}), encoding="utf-8")

    exit_code = eval_module.main(["--case-file", str(case_file)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "Eval config error:" in captured.err


def test_main_returns_one_when_average_score_below_minimum(monkeypatch, capsys) -> None:
    payload = {
        "cases": [],
        "summary": {
            "case_count": 1,
            "average_score": 72,
            "passed_count": 0,
            "failed_count": 1,
            "failed_rules": {},
            "total_duration_ms": 0,
            "all_critique_passed": False,
            "total_findings": 0,
            "total_competitive_matrix_rows": 0,
            "total_references": 0,
            "total_tool_calls": 0,
            "total_llm_calls": 0,
        },
    }
    monkeypatch.setattr(eval_module, "build_eval_payload", lambda cases=None: payload)

    exit_code = eval_module.main(["--min-score", "80"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Eval gate failed: average score 72 < 80" in captured.err
    assert '"average_score": 72' in captured.out


def test_main_returns_one_when_any_case_fails(monkeypatch, capsys) -> None:
    payload = {
        "cases": [],
        "summary": {
            "case_count": 2,
            "average_score": 90,
            "passed_count": 1,
            "failed_count": 1,
            "failed_rules": {},
            "total_duration_ms": 0,
            "all_critique_passed": False,
            "total_findings": 0,
            "total_competitive_matrix_rows": 0,
            "total_references": 0,
            "total_tool_calls": 0,
            "total_llm_calls": 0,
        },
    }
    monkeypatch.setattr(eval_module, "build_eval_payload", lambda cases=None: payload)

    exit_code = eval_module.main(["--fail-on-case-failure"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Eval gate failed: 1 case(s) failed" in captured.err


def test_main_writes_output_before_gate_failure(monkeypatch, tmp_path) -> None:
    payload = {
        "cases": [],
        "summary": {
            "case_count": 1,
            "average_score": 72,
            "passed_count": 0,
            "failed_count": 1,
            "failed_rules": {},
            "total_duration_ms": 0,
            "all_critique_passed": False,
            "total_findings": 0,
            "total_competitive_matrix_rows": 0,
            "total_references": 0,
            "total_tool_calls": 0,
            "total_llm_calls": 0,
        },
    }
    output_path = tmp_path / "eval.json"
    monkeypatch.setattr(eval_module, "build_eval_payload", lambda cases=None: payload)

    exit_code = eval_module.main(["--output", str(output_path), "--min-score", "80"])

    assert exit_code == 1
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_default_eval_case_file_loads_expected_cases() -> None:
    case_path = eval_module.Path(__file__).parents[1] / "docs" / "evals" / "default.json"

    cases = eval_module.load_eval_cases(case_path)

    assert [case.query for case in cases] == [
        "Compare Cursor, OpenCode, and GitHub Copilot",
        "Analyze AI coding agents market positioning",
        "Compare Claude Code, Codeium, and Windsurf",
    ]
    assert [case.min_findings for case in cases] == [1, 1, 1]
    assert [case.min_matrix_rows for case in cases] == [1, 1, 1]
    assert [case.min_references for case in cases] == [2, 2, 2]


def test_pyproject_registers_eval_console_script() -> None:
    pyproject = (eval_module.Path(__file__).parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )

    assert 'insight-graph-eval = "insight_graph.eval:main"' in pyproject
