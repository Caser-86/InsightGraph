import io
import json
import os

from scripts.validate_pdf_fetch import format_markdown, main, run_validation


class BadStdout:
    def write(self, value: str) -> int:
        raise OSError("cannot write")


def case_by_name(payload: dict, name: str) -> dict:
    return next(case for case in payload["cases"] if case["name"] == name)


def test_run_validation_returns_fixed_cases():
    payload = run_validation()

    assert [case["name"] for case in payload["cases"]] == [
        "document_reader_pdf_success",
        "search_document_pdf_query_success",
        "search_document_pdf_page_success",
        "fetch_url_remote_pdf_success",
        "fetch_url_remote_pdf_query_success",
        "bad_remote_pdf_returns_empty",
        "empty_remote_pdf_returns_empty",
    ]


def test_run_validation_summary_counts_results():
    payload = run_validation()

    assert payload["summary"] == {
        "case_count": 7,
        "passed_count": 7,
        "failed_count": 0,
        "all_passed": True,
        "total_evidence_count": 5,
    }


def test_run_validation_success_cases_include_expected_metadata():
    payload = run_validation()

    local_case = case_by_name(payload, "document_reader_pdf_success")
    assert local_case["passed"] is True
    assert local_case["title"] == "local.pdf"
    assert local_case["source_type"] == "docs"
    assert local_case["verified"] is True
    assert local_case["source_url_scheme"] == "file"
    assert local_case["chunk_index"] == 1
    assert local_case["document_page"] == 1
    assert local_case["snippet_contains"] is True
    assert local_case["error"] is None

    query_case = case_by_name(payload, "search_document_pdf_query_success")
    assert query_case["title"] == "searchable.pdf (chunk 4)"
    assert query_case["chunk_index"] == 4
    assert query_case["document_page"] == 2
    assert query_case["snippet_contains"] is True

    page_case = case_by_name(payload, "search_document_pdf_page_success")
    assert page_case["title"] == "searchable.pdf (chunk 4)"
    assert page_case["chunk_index"] == 4
    assert page_case["document_page"] == 2
    assert page_case["snippet_contains"] is True

    remote_case = case_by_name(payload, "fetch_url_remote_pdf_success")
    assert remote_case["title"] == "remote.pdf"
    assert remote_case["source_url_scheme"] == "https"
    assert remote_case["document_page"] == 1
    assert remote_case["snippet_contains"] is True

    remote_query_case = case_by_name(payload, "fetch_url_remote_pdf_query_success")
    assert remote_query_case["title"] == "remote-searchable.pdf"
    assert remote_query_case["document_page"] == 2
    assert remote_query_case["snippet_contains"] is True


def test_run_validation_empty_cases_pass_with_no_evidence():
    payload = run_validation()
    for name in ["bad_remote_pdf_returns_empty", "empty_remote_pdf_returns_empty"]:
        case = case_by_name(payload, name)
        assert case["passed"] is True
        assert case["evidence_count"] == 0
        assert case["expected_evidence_count"] == 0
        assert case["title"] is None
        assert case["source_type"] is None
        assert case["verified"] is None
        assert case["source_url_scheme"] is None
        assert case["chunk_index"] is None
        assert case["document_page"] is None
        assert case["snippet_contains"] is None
        assert case["error"] is None


def test_run_validation_restores_cwd_after_success():
    original_cwd = os.getcwd()

    run_validation()

    assert os.getcwd() == original_cwd


def test_format_markdown_writes_summary_table():
    payload = run_validation()

    output = format_markdown(payload)

    assert output.startswith("# PDF Fetch Validation")
    success_row = (
        "| document_reader_pdf_success | true | 1 | 1 | local.pdf | docs | true | file | "
        "1 | 1 | true |  |"
    )
    assert success_row in output
    assert "## Summary" in output
    assert "| 7 | 7 | 0 | true | 5 |" in output
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
                "chunk_index": 1,
                "document_page": 2,
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
    assert payload["summary"]["case_count"] == 7


def test_main_writes_markdown_when_flag_is_present():
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(["--markdown"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert stdout.getvalue().startswith("# PDF Fetch Validation")
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
    assert "PDF fetch validation failed: failed to write output" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()
