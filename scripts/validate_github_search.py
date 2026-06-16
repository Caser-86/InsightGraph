from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, TextIO
from urllib.parse import urlparse

from insight_graph.state import Evidence
from insight_graph.tools.github_search import github_search

github_search_module = importlib.import_module("insight_graph.tools.github_search")

CASE_ERROR = "GitHub search validation case failed."
SCRIPT_ERROR_PREFIX = "GitHub search validation failed"


class ValidationArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, stderr: TextIO, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stderr = stderr

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message:
            self._stderr.write(message)
        raise SystemExit(status)

    def error(self, message: str) -> None:
        self.print_usage(self._stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


@dataclass(frozen=True)
class ValidationCase:
    name: str
    provider: str
    query: str
    expected_evidence_count: int
    expected_first_title: str


SearchFn = Callable[[str, str], list[Evidence]]


def run_validation(search: SearchFn = github_search) -> dict[str, Any]:
    cases = [
        ValidationCase(
            "mock_provider_success",
            "mock",
            "Compare Cursor, OpenCode, and GitHub Copilot",
            3,
            "OpenCode Repository",
        ),
        ValidationCase(
            "live_provider_fake_success",
            "live-fake",
            "InsightGraph competitive intelligence",
            3,
            "example/insightgraph",
        ),
    ]
    case_results = [_run_case(case, search) for case in cases]
    return {
        "cases": case_results,
        "summary": _summary(case_results),
    }


def _run_case(case: ValidationCase, search: SearchFn) -> dict[str, Any]:
    try:
        with _case_environment(case, search):
            evidence = search(case.query, "collect")
    except Exception:
        return _case_payload(case, [], passed=False, error=CASE_ERROR)

    passed = _case_passed(case, evidence)
    return _case_payload(case, evidence, passed=passed, error=None if passed else CASE_ERROR)


@contextmanager
def _case_environment(case: ValidationCase, search: SearchFn) -> Iterator[None]:
    previous_provider = os.environ.get("INSIGHT_GRAPH_GITHUB_PROVIDER")
    previous_limit = os.environ.get("INSIGHT_GRAPH_GITHUB_LIMIT")
    previous_details = os.environ.get("INSIGHT_GRAPH_GITHUB_FETCH_DETAILS")
    original_fetch = github_search_module.fetch_github_json
    original_headers = github_search_module._github_headers
    try:
        if case.provider == "mock":
            os.environ.pop("INSIGHT_GRAPH_GITHUB_PROVIDER", None)
            os.environ.pop("INSIGHT_GRAPH_GITHUB_LIMIT", None)
            os.environ.pop("INSIGHT_GRAPH_GITHUB_FETCH_DETAILS", None)
        else:
            os.environ["INSIGHT_GRAPH_GITHUB_PROVIDER"] = "live"
            os.environ["INSIGHT_GRAPH_GITHUB_LIMIT"] = "1"
            os.environ["INSIGHT_GRAPH_GITHUB_FETCH_DETAILS"] = "1"
            if search is github_search:
                github_search_module.fetch_github_json = _fake_github_json
                github_search_module._github_headers = _fake_github_headers
        yield
    finally:
        github_search_module.fetch_github_json = original_fetch
        github_search_module._github_headers = original_headers
        _restore_env("INSIGHT_GRAPH_GITHUB_PROVIDER", previous_provider)
        _restore_env("INSIGHT_GRAPH_GITHUB_LIMIT", previous_limit)
        _restore_env("INSIGHT_GRAPH_GITHUB_FETCH_DETAILS", previous_details)


def _fake_github_json(
    url: str,
    headers: dict[str, str],
    timeout: float,
):
    if url == "https://api.github.com/repos/example/insightgraph/readme":
        return {
            "html_url": "https://github.com/example/insightgraph#readme",
            "content": "T2ZmbGluZSBmYWtlIFJFQURNRSBldmlkZW5jZS4=",
            "encoding": "base64",
        }
    if url == "https://api.github.com/repos/example/insightgraph/releases?per_page=1":
        return [
            {
                "name": "v0.1.0",
                "tag_name": "v0.1.0",
                "html_url": "https://github.com/example/insightgraph/releases/tag/v0.1.0",
                "body": "Offline fake release evidence.",
                "published_at": "2026-04-27T00:00:00Z",
            }
        ]
    return {
        "items": [
            {
                "full_name": "example/insightgraph",
                "html_url": "https://github.com/example/insightgraph",
                "description": "Offline fake GitHub API response for validator.",
                "stargazers_count": 42,
                "language": "Python",
                "updated_at": "2026-04-27T00:00:00Z",
            }
        ]
    }


def _fake_github_headers() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": "InsightGraph/0.1",
    }


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def _case_passed(case: ValidationCase, evidence: list[Evidence]) -> bool:
    if len(evidence) != case.expected_evidence_count:
        return False
    if not evidence:
        return False
    item = evidence[0]
    return (
        item.title == case.expected_first_title
        and item.source_type == "github"
        and item.verified is True
        and urlparse(item.source_url).netloc == "github.com"
    )


def _case_payload(
    case: ValidationCase,
    evidence: list[Evidence],
    *,
    passed: bool,
    error: str | None,
) -> dict[str, Any]:
    item = evidence[0] if evidence else None
    return {
        "name": case.name,
        "query": case.query,
        "provider": case.provider,
        "passed": passed,
        "evidence_count": len(evidence),
        "expected_evidence_count": case.expected_evidence_count,
        "first_title": item.title if item else None,
        "source_type": item.source_type if item else None,
        "verified": item.verified if item else None,
        "source_url_host": urlparse(item.source_url).netloc if item else None,
        "error": error,
    }


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    passed_count = sum(1 for case in cases if case["passed"])
    return {
        "case_count": len(cases),
        "passed_count": passed_count,
        "failed_count": len(cases) - passed_count,
        "all_passed": passed_count == len(cases),
        "total_evidence_count": sum(case["evidence_count"] for case in cases),
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# GitHub Search Validation",
        "",
        (
            "| Case | Passed | Provider | Evidence | Expected | First title | "
            "Source type | Verified | Host | Error |"
        ),
        "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for case in payload["cases"]:
        lines.append(
            "| "
            f"{_markdown_cell(case['name'])} | "
            f"{_markdown_bool(case['passed'])} | "
            f"{_markdown_cell(case['provider'])} | "
            f"{case['evidence_count']} | "
            f"{case['expected_evidence_count']} | "
            f"{_markdown_cell(case['first_title'])} | "
            f"{_markdown_cell(case['source_type'])} | "
            f"{_markdown_bool(case['verified'])} | "
            f"{_markdown_cell(case['source_url_host'])} | "
            f"{_markdown_cell(case['error'])} |"
        )

    summary = payload["summary"]
    lines.extend(
        [
            "",
            "## Summary",
            "",
            "| Cases | Passed | Failed | All passed | Total evidence |",
            "| ---: | ---: | ---: | --- | ---: |",
            "| "
            f"{summary['case_count']} | "
            f"{summary['passed_count']} | "
            f"{summary['failed_count']} | "
            f"{_markdown_bool(summary['all_passed'])} | "
            f"{summary['total_evidence_count']} |",
        ]
    )
    return "\n".join(lines) + "\n"


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = ValidationArgumentParser(
        description="Validate github_search providers with offline fixtures.",
        stderr=stderr,
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Write GitHub-flavored Markdown output.",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    payload = run_validation()

    try:
        if args.markdown:
            stdout.write(format_markdown(payload))
        else:
            json.dump(payload, stdout, indent=2, ensure_ascii=False)
            stdout.write("\n")
    except OSError:
        stderr.write(f"{SCRIPT_ERROR_PREFIX}: failed to write output\n")
        return 2

    return 0 if payload["summary"]["all_passed"] else 1


def _markdown_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", r"\|")


def _markdown_bool(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return _markdown_cell(value)


if __name__ == "__main__":
    raise SystemExit(main())
