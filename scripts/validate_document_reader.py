from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from insight_graph.state import Evidence
from insight_graph.tools.document_reader import document_reader

CASE_ERROR = "Document reader validation case failed."


@dataclass(frozen=True)
class ValidationCase:
    name: str
    query: str
    expected_evidence_count: int
    expected_title: str | None = None
    expected_snippet: str | None = None


def run_validation(
    reader: Callable[[str], list[Evidence]] = document_reader,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="insightgraph-document-reader-") as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "insightgraph-document-reader-validation"
        outside_file = temp_path / "outside.md"
        _write_fixtures(workspace, outside_file)

        cases = _validation_cases(outside_file)
        with _temporary_cwd(workspace):
            case_results = [_run_case(case, reader) for case in cases]

    return {
        "cases": case_results,
        "summary": _summary(case_results),
    }


def _write_fixtures(workspace: Path, outside_file: Path) -> None:
    nested = workspace / "nested"
    nested.mkdir(parents=True)
    (workspace / "notes.txt").write_text(
        "These offline notes validate document_reader TXT support.",
        encoding="utf-8",
    )
    (workspace / "market.md").write_text(
        "# Markdown market brief\n\nMarkdown market brief content.",
        encoding="utf-8",
    )
    (workspace / "appendix.markdown").write_text(
        "# Appendix\n\nMarkdown appendix content.",
        encoding="utf-8",
    )
    (workspace / "unsupported.pdf").write_text("not a real PDF", encoding="utf-8")
    (workspace / "empty.txt").write_text("", encoding="utf-8")
    (workspace / "invalid.txt").write_bytes(b"\xff\xfe\x00")
    (nested / "deep.md").write_text("nested document content", encoding="utf-8")
    outside_file.write_text("outside document", encoding="utf-8")


def _validation_cases(outside_file: Path) -> list[ValidationCase]:
    return [
        ValidationCase("txt_file_success", "notes.txt", 1, "notes.txt", "offline notes"),
        ValidationCase(
            "markdown_file_success",
            "market.md",
            1,
            "market.md",
            "Markdown market brief",
        ),
        ValidationCase(
            "markdown_suffix_success",
            "appendix.markdown",
            1,
            "appendix.markdown",
            "Markdown appendix",
        ),
        ValidationCase("nested_file_success", "nested/deep.md", 1, "deep.md", "nested document"),
        ValidationCase("unsupported_suffix_returns_empty", "unsupported.pdf", 0),
        ValidationCase("missing_file_returns_empty", "missing.md", 0),
        ValidationCase("empty_file_returns_empty", "empty.txt", 0),
        ValidationCase("invalid_utf8_returns_empty", "invalid.txt", 0),
        ValidationCase("outside_root_returns_empty", str(outside_file), 0),
        ValidationCase("parent_traversal_returns_empty", "../outside.md", 0),
    ]


def _run_case(
    case: ValidationCase,
    reader: Callable[[str], list[Evidence]],
) -> dict[str, Any]:
    try:
        evidence = reader(case.query)
    except Exception:
        return _case_payload(case, [], passed=False, error=CASE_ERROR)

    passed = _case_passed(case, evidence)
    return _case_payload(case, evidence, passed=passed, error=None if passed else CASE_ERROR)


def _case_passed(case: ValidationCase, evidence: list[Evidence]) -> bool:
    if len(evidence) != case.expected_evidence_count:
        return False
    if case.expected_evidence_count == 0:
        return True

    item = evidence[0]
    return (
        item.title == case.expected_title
        and item.source_type == "docs"
        and item.verified is True
        and urlparse(item.source_url).scheme == "file"
        and case.expected_snippet is not None
        and case.expected_snippet in item.snippet
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
        "passed": passed,
        "evidence_count": len(evidence),
        "expected_evidence_count": case.expected_evidence_count,
        "title": item.title if item else None,
        "source_type": item.source_type if item else None,
        "verified": item.verified if item else None,
        "source_url_scheme": urlparse(item.source_url).scheme if item else None,
        "snippet_contains": _snippet_contains(case, item),
        "error": error,
    }


def _snippet_contains(case: ValidationCase, item: Evidence | None) -> bool | None:
    if item is None or case.expected_snippet is None:
        return None
    return case.expected_snippet in item.snippet


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    passed_count = sum(1 for case in cases if case["passed"])
    return {
        "case_count": len(cases),
        "passed_count": passed_count,
        "failed_count": len(cases) - passed_count,
        "all_passed": passed_count == len(cases),
        "total_evidence_count": sum(case["evidence_count"] for case in cases),
    }


@contextmanager
def _temporary_cwd(path: Path) -> Iterator[None]:
    original_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original_cwd)
