import io
import json
import os

from scripts.validate_document_reader import format_markdown, main, run_validation


class BadStdout:
    def write(self, value: str) -> int:
        raise OSError("cannot write")


def case_by_name(payload: dict, name: str) -> dict:
    return next(case for case in payload["cases"] if case["name"] == name)


def test_run_validation_returns_fixed_cases():
    payload = run_validation()

    assert [case["name"] for case in payload["cases"]] == [
        "txt_file_success",
        "long_file_chunking_success",
        "json_query_ranking_success",
        "markdown_file_success",
        "markdown_suffix_success",
        "html_file_success",
        "pdf_file_success",
        "nested_file_success",
        "unsupported_suffix_returns_empty",
        "missing_file_returns_empty",
        "empty_file_returns_empty",
        "invalid_utf8_returns_empty",
        "outside_root_returns_empty",
        "parent_traversal_returns_empty",
    ]


def test_run_validation_success_cases_include_expected_metadata():
    payload = run_validation()

    txt_case = case_by_name(payload, "txt_file_success")
    assert txt_case["passed"] is True
    assert txt_case["evidence_count"] == 1
    assert txt_case["expected_evidence_count"] == 1
    assert txt_case["title"] == "notes.txt"
    assert txt_case["source_type"] == "docs"
    assert txt_case["verified"] is True
    assert txt_case["source_url_scheme"] == "file"
    assert txt_case["snippet_contains"] is True
    assert txt_case["error"] is None

    long_case = case_by_name(payload, "long_file_chunking_success")
    assert long_case["title"] == "long.txt"
    assert long_case["snippet_contains"] is True

    ranked_case = case_by_name(payload, "json_query_ranking_success")
    assert ranked_case["title"] == "ranked.txt (chunk 3)"
    assert ranked_case["snippet_contains"] is True

    markdown_case = case_by_name(payload, "markdown_file_success")
    assert markdown_case["title"] == "market.md"
    assert markdown_case["snippet_contains"] is True

    suffix_case = case_by_name(payload, "markdown_suffix_success")
    assert suffix_case["title"] == "appendix.markdown"
    assert suffix_case["snippet_contains"] is True

    html_case = case_by_name(payload, "html_file_success")
    assert html_case["title"] == "brief.html"
    assert html_case["snippet_contains"] is True

    pdf_case = case_by_name(payload, "pdf_file_success")
    assert pdf_case["title"] == "brief.pdf"
    assert pdf_case["snippet_contains"] is True

    nested_case = case_by_name(payload, "nested_file_success")
    assert nested_case["title"] == "deep.md"
    assert nested_case["snippet_contains"] is True


def test_run_validation_empty_cases_pass_with_no_evidence():
    payload = run_validation()
    empty_case_names = [
        "unsupported_suffix_returns_empty",
        "missing_file_returns_empty",
        "empty_file_returns_empty",
        "invalid_utf8_returns_empty",
        "outside_root_returns_empty",
        "parent_traversal_returns_empty",
    ]

    for name in empty_case_names:
        case = case_by_name(payload, name)
        assert case["passed"] is True
        assert case["evidence_count"] == 0
        assert case["expected_evidence_count"] == 0
        assert case["title"] is None
        assert case["source_type"] is None
        assert case["verified"] is None
        assert case["source_url_scheme"] is None
        assert case["snippet_contains"] is None
        assert case["error"] is None


def test_run_validation_summary_counts_results():
    payload = run_validation()

    assert payload["summary"] == {
        "case_count": 14,
        "passed_count": 14,
        "failed_count": 0,
        "all_passed": True,
        "total_evidence_count": 14,
    }


def test_run_validation_restores_cwd_after_success():
    original_cwd = os.getcwd()

    run_validation()

    assert os.getcwd() == original_cwd


def test_run_validation_restores_cwd_after_case_exception():
    original_cwd = os.getcwd()

    def failing_reader(query: str):
        raise RuntimeError("raw reader failure should not leak")

    payload = run_validation(reader=failing_reader)

    assert os.getcwd() == original_cwd
    assert payload["summary"] == {
        "case_count": 14,
        "passed_count": 0,
        "failed_count": 14,
        "all_passed": False,
        "total_evidence_count": 0,
    }
    assert {case["error"] for case in payload["cases"]} == {
        "Document reader validation case failed."
    }
    assert "raw reader failure" not in json.dumps(payload)


def test_format_markdown_writes_summary_table():
    payload = run_validation()

    output = format_markdown(payload)
    case_header = (
        "| Case | Passed | Evidence | Expected | Title | Source type | Verified | "
        "URL scheme | Snippet check | Error |"
    )
    success_row = "| txt_file_success | true | 1 | 1 | notes.txt | docs | true | file | true |  |"

    assert output.startswith("# Document Reader Validation")
    assert case_header in output
    assert success_row in output
    assert "## Summary" in output
    assert "| 14 | 14 | 0 | true | 14 |" in output
    assert output.endswith("\n")


def test_format_markdown_escapes_table_cells():
    payload = {
        "cases": [
            {
                "name": "case|one",
                "query": "query",
                "passed": False,
                "evidence_count": 0,
                "expected_evidence_count": 1,
                "title": "title|value",
                "source_type": "docs",
                "verified": False,
                "source_url_scheme": "file",
                "snippet_contains": False,
                "error": "line one | line two\nline three",
            }
        ],
        "summary": {
            "case_count": 1,
            "passed_count": 0,
            "failed_count": 1,
            "all_passed": False,
            "total_evidence_count": 0,
        },
    }

    output = format_markdown(payload)

    assert "case\\|one" in output
    assert "title\\|value" in output
    assert "line one \\| line two line three" in output


def test_main_writes_json_by_default():
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main([], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert payload["summary"]["all_passed"] is True
    assert payload["summary"]["case_count"] == 14


def test_main_writes_markdown_when_flag_is_present():
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(["--markdown"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert stdout.getvalue().startswith("# Document Reader Validation")
    assert "## Summary" in stdout.getvalue()


def test_main_returns_two_for_parse_error_without_traceback():
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(["--unknown"], stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "usage:" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()


def test_main_returns_two_for_stdout_write_error_without_traceback():
    stderr = io.StringIO()

    exit_code = main([], stdout=BadStdout(), stderr=stderr)

    assert exit_code == 2
    assert "Document reader validation failed: failed to write output" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()
