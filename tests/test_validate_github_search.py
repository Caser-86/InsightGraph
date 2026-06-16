import importlib
import io
import json

from insight_graph.state import Evidence
from scripts.validate_github_search import format_markdown, main, run_validation


class BadStdout:
    def write(self, value: str) -> int:
        raise OSError("cannot write")


def case_by_name(payload: dict, name: str) -> dict:
    return next(case for case in payload["cases"] if case["name"] == name)


def test_run_validation_returns_offline_cases() -> None:
    payload = run_validation()

    assert [case["name"] for case in payload["cases"]] == [
        "mock_provider_success",
        "live_provider_fake_success",
    ]


def test_run_validation_success_cases_include_expected_metadata() -> None:
    payload = run_validation()

    mock_case = case_by_name(payload, "mock_provider_success")
    assert mock_case["passed"] is True
    assert mock_case["provider"] == "mock"
    assert mock_case["evidence_count"] == 3
    assert mock_case["expected_evidence_count"] == 3
    assert mock_case["first_title"] == "OpenCode Repository"
    assert mock_case["source_type"] == "github"
    assert mock_case["verified"] is True
    assert mock_case["source_url_host"] == "github.com"
    assert mock_case["error"] is None

    live_case = case_by_name(payload, "live_provider_fake_success")
    assert live_case["passed"] is True
    assert live_case["provider"] == "live-fake"
    assert live_case["evidence_count"] == 3
    assert live_case["expected_evidence_count"] == 3
    assert live_case["first_title"] == "example/insightgraph"
    assert live_case["source_type"] == "github"
    assert live_case["verified"] is True
    assert live_case["source_url_host"] == "github.com"
    assert live_case["error"] is None


def test_run_validation_summary_counts_results() -> None:
    payload = run_validation()

    assert payload["summary"] == {
        "case_count": 2,
        "passed_count": 2,
        "failed_count": 0,
        "all_passed": True,
        "total_evidence_count": 6,
    }


def test_run_validation_sanitizes_case_exceptions() -> None:
    def failing_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
        raise RuntimeError("raw GitHub token and local path")

    payload = run_validation(search=failing_search)

    assert payload["summary"] == {
        "case_count": 2,
        "passed_count": 0,
        "failed_count": 2,
        "all_passed": False,
        "total_evidence_count": 0,
    }
    assert {case["error"] for case in payload["cases"]} == {
        "GitHub search validation case failed."
    }
    assert "raw GitHub token" not in json.dumps(payload)
    assert "local path" not in json.dumps(payload)


def test_run_validation_fake_live_does_not_use_token_headers(monkeypatch) -> None:
    github_search_module = importlib.import_module("insight_graph.tools.github_search")

    def fail_headers() -> dict[str, str]:
        raise RuntimeError("token header path should not run")

    monkeypatch.setenv("INSIGHT_GRAPH_GITHUB_TOKEN", "secret-token")
    monkeypatch.setattr(github_search_module, "_github_headers", fail_headers)

    payload = run_validation()

    assert payload["summary"]["all_passed"] is True
    assert "secret-token" not in json.dumps(payload)
    assert "token header path" not in json.dumps(payload)


def test_format_markdown_writes_summary_table() -> None:
    output = format_markdown(run_validation())

    assert output.startswith("# GitHub Search Validation")
    assert (
        "| Case | Passed | Provider | Evidence | Expected | First title | "
        "Source type | Verified | Host | Error |"
    ) in output
    assert (
        "| mock_provider_success | true | mock | 3 | 3 | "
        "OpenCode Repository | github | true | github.com |  |"
    ) in output
    assert "## Summary" in output
    assert "| 2 | 2 | 0 | true | 6 |" in output
    assert output.endswith("\n")


def test_format_markdown_escapes_table_cells() -> None:
    payload = {
        "cases": [
            {
                "name": "case|one",
                "query": "query",
                "provider": "mock",
                "passed": False,
                "evidence_count": 0,
                "expected_evidence_count": 1,
                "first_title": "title|value",
                "source_type": "github",
                "verified": False,
                "source_url_host": "github.com",
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


def test_main_writes_json_by_default() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main([], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert payload["summary"]["all_passed"] is True
    assert payload["summary"]["case_count"] == 2


def test_main_writes_markdown_when_flag_is_present() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(["--markdown"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert stdout.getvalue().startswith("# GitHub Search Validation")
    assert "## Summary" in stdout.getvalue()


def test_main_returns_two_for_parse_error_without_traceback() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(["--unknown"], stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "usage:" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()


def test_main_returns_two_for_stdout_write_error_without_traceback() -> None:
    stderr = io.StringIO()

    exit_code = main([], stdout=BadStdout(), stderr=stderr)

    assert exit_code == 2
    assert "GitHub search validation failed: failed to write output" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()
