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
