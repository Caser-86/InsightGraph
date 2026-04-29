import io
import json

import scripts.summarize_eval_report as summary_module

EVAL_PAYLOAD = {
    "cases": [],
    "summary": {
        "case_count": 3,
        "average_score": 91.5,
        "passed_count": 2,
        "failed_count": 1,
        "failed_rules": {"references_meet_minimum": 1},
        "total_duration_ms": 23,
        "all_critique_passed": False,
        "total_findings": 6,
        "total_competitive_matrix_rows": 9,
        "total_references": 8,
        "total_tool_calls": 3,
        "total_llm_calls": 0,
    },
}


def test_summarize_eval_report_extracts_summary_subset() -> None:
    assert summary_module.summarize_eval_report(EVAL_PAYLOAD) == {
        "case_count": 3,
        "average_score": 91.5,
        "passed_count": 2,
        "failed_count": 1,
        "failed_rules": {"references_meet_minimum": 1},
        "total_duration_ms": 23,
    }


def test_format_markdown_outputs_compact_summary_table() -> None:
    markdown = summary_module.format_markdown(
        summary_module.summarize_eval_report(EVAL_PAYLOAD)
    )

    assert "# Eval Summary" in markdown
    assert "| Cases | Average score | Passed | Failed | Duration ms |" in markdown
    assert "| 3 | 91.5 | 2 | 1 | 23 |" in markdown
    assert "## Failed Rules" in markdown
    assert "| references_meet_minimum | 1 |" in markdown


def test_main_reads_eval_report_and_prints_json(tmp_path) -> None:
    report_path = tmp_path / "eval.json"
    report_path.write_text(json.dumps(EVAL_PAYLOAD), encoding="utf-8")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = summary_module.main([str(report_path)], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == {
        "case_count": 3,
        "average_score": 91.5,
        "passed_count": 2,
        "failed_count": 1,
        "failed_rules": {"references_meet_minimum": 1},
        "total_duration_ms": 23,
    }
    assert stderr.getvalue() == ""


def test_main_returns_two_for_malformed_json(tmp_path) -> None:
    report_path = tmp_path / "eval.json"
    report_path.write_text("not json", encoding="utf-8")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = summary_module.main([str(report_path)], stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "Failed to read eval report:" in stderr.getvalue()
