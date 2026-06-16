from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import urlparse

from insight_graph.state import Evidence
from insight_graph.tools.document_reader import document_reader

CASE_ERROR = "Document reader validation case failed."
SCRIPT_ERROR_PREFIX = "Document reader validation failed"


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
    (workspace / "long.txt").write_text(
        "".join(str(index % 10) for index in range(2200)),
        encoding="utf-8",
    )
    (workspace / "ranked.txt").write_text(
        ("alpha " * 100) + ("enterprise pricing " * 40),
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
    (workspace / "brief.html").write_text(
        """
        <html>
          <head><style>.x { color: red; }</style></head>
          <body><h1>HTML market brief</h1><p>HTML document_reader support.</p></body>
        </html>
        """,
        encoding="utf-8",
    )
    _write_minimal_pdf(workspace / "brief.pdf", "PDF market brief for document_reader.")
    (workspace / "unsupported.docx").write_text("not a supported document", encoding="utf-8")
    (workspace / "empty.txt").write_text("", encoding="utf-8")
    (workspace / "invalid.txt").write_bytes(b"\xff\xfe\x00")
    (nested / "deep.md").write_text("nested document content", encoding="utf-8")
    outside_file.write_text("outside document", encoding="utf-8")


def _write_minimal_pdf(path: Path, text: str) -> None:
    escaped_text = text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")
    content = f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content.encode())} >>\nstream\n{content}\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n{body}\nendobj\n".encode())
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    path.write_bytes(bytes(output))


def _validation_cases(outside_file: Path) -> list[ValidationCase]:
    return [
        ValidationCase("txt_file_success", "notes.txt", 1, "notes.txt", "offline notes"),
        ValidationCase("long_file_chunking_success", "long.txt", 5, "long.txt", "0123456789"),
        ValidationCase(
            "json_query_ranking_success",
            '{"path":"ranked.txt","query":"enterprise pricing"}',
            3,
            "ranked.txt (chunk 3)",
            "enterprise pricing",
        ),
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
        ValidationCase(
            "html_file_success",
            "brief.html",
            1,
            "brief.html",
            "HTML market brief",
        ),
        ValidationCase(
            "pdf_file_success",
            "brief.pdf",
            1,
            "brief.pdf",
            "PDF market brief",
        ),
        ValidationCase("nested_file_success", "nested/deep.md", 1, "deep.md", "nested document"),
        ValidationCase("unsupported_suffix_returns_empty", "unsupported.docx", 0),
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


def format_markdown(payload: dict[str, Any]) -> str:
    case_header = (
        "| Case | Passed | Evidence | Expected | Title | Source type | Verified | "
        "URL scheme | Snippet check | Error |"
    )
    lines = [
        "# Document Reader Validation",
        "",
        case_header,
        "| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for case in payload["cases"]:
        lines.append(
            "| "
            f"{_markdown_cell(case['name'])} | "
            f"{_markdown_bool(case['passed'])} | "
            f"{case['evidence_count']} | "
            f"{case['expected_evidence_count']} | "
            f"{_markdown_cell(case['title'])} | "
            f"{_markdown_cell(case['source_type'])} | "
            f"{_markdown_bool(case['verified'])} | "
            f"{_markdown_cell(case['source_url_scheme'])} | "
            f"{_markdown_bool(case['snippet_contains'])} | "
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
        description="Validate the local document_reader tool with offline fixtures.",
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

    try:
        payload = run_validation()
    except OSError:
        stderr.write(f"{SCRIPT_ERROR_PREFIX}: failed to prepare validation workspace\n")
        return 2

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
