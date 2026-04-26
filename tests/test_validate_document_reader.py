import os

from scripts.validate_document_reader import run_validation


def case_by_name(payload: dict, name: str) -> dict:
    return next(case for case in payload["cases"] if case["name"] == name)


def test_run_validation_returns_fixed_cases():
    payload = run_validation()

    assert [case["name"] for case in payload["cases"]] == [
        "txt_file_success",
        "markdown_file_success",
        "markdown_suffix_success",
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

    markdown_case = case_by_name(payload, "markdown_file_success")
    assert markdown_case["title"] == "market.md"
    assert markdown_case["snippet_contains"] is True

    suffix_case = case_by_name(payload, "markdown_suffix_success")
    assert suffix_case["title"] == "appendix.markdown"
    assert suffix_case["snippet_contains"] is True

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
        "case_count": 10,
        "passed_count": 10,
        "failed_count": 0,
        "all_passed": True,
        "total_evidence_count": 4,
    }


def test_run_validation_restores_cwd_after_success():
    original_cwd = os.getcwd()

    run_validation()

    assert os.getcwd() == original_cwd
