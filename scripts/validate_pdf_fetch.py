from __future__ import annotations

import argparse
import importlib
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
from insight_graph.tools import fetch_url as fetch_url_tool
from insight_graph.tools.document_reader import document_reader
from insight_graph.tools.http_client import FetchedPage
from insight_graph.tools.search_document import search_document

CASE_ERROR = "PDF fetch validation case failed."
SCRIPT_ERROR_PREFIX = "PDF fetch validation failed"


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
    runner: Callable[[], list[Evidence]]
    query: str
    expected_evidence_count: int
    expected_title: str | None = None
    expected_snippet: str | None = None
    expected_source_url_scheme: str | None = None
    expected_document_page: int | None = None
    expected_chunk_index: int | None = 1


def run_validation() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="insightgraph-pdf-fetch-") as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "insightgraph-pdf-fetch-validation"
        _write_fixtures(workspace)
        with _temporary_cwd(workspace):
            cases = _validation_cases(workspace)
            case_results = [_run_case(case) for case in cases]
    return {"cases": case_results, "summary": _summary(case_results)}


def _write_fixtures(workspace: Path) -> None:
    workspace.mkdir(parents=True)
    long_alpha = "Local PDF alpha evidence. " * 45
    long_beta = "Local PDF beta page evidence. " * 45
    long_remote_alpha = "Remote PDF alpha evidence. " * 45
    long_remote_pricing = "Remote PDF pricing page evidence. " * 45
    _write_minimal_pdf(workspace / "local.pdf", "Local PDF alpha evidence.")
    _write_minimal_pdf(workspace / "searchable.pdf", f"{long_alpha}\f{long_beta}")
    _write_minimal_pdf(workspace / "remote.pdf", "Remote PDF alpha evidence.")
    _write_minimal_pdf(
        workspace / "remote-searchable.pdf",
        f"{long_remote_alpha}\f{long_remote_pricing}",
    )
    (workspace / "bad.pdf").write_bytes(b"%PDF-1.4\nnot a valid pdf")
    (workspace / "empty.pdf").write_bytes(b"")


def _write_minimal_pdf(path: Path, text: str) -> None:
    pages = text.split("\f")
    objects = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = []
    page_objects = []
    font_obj = 3 + len(pages) * 2
    for page_index, page_text in enumerate(pages):
        page_obj = 3 + page_index * 2
        content_obj = page_obj + 1
        kids.append(f"{page_obj} 0 R")
        escaped_text = page_text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")
        content = f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET"
        page_objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
            f"/Contents {content_obj} 0 R >>"
        )
        page_objects.append(f"<< /Length {len(content.encode())} >>\nstream\n{content}\nendstream")
    objects.append(f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>")
    objects.extend(page_objects)
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
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


def _validation_cases(workspace: Path) -> list[ValidationCase]:
    remote_bytes = (workspace / "remote.pdf").read_bytes()
    remote_searchable_bytes = (workspace / "remote-searchable.pdf").read_bytes()
    bad_bytes = (workspace / "bad.pdf").read_bytes()
    empty_bytes = (workspace / "empty.pdf").read_bytes()
    return [
        ValidationCase(
            "document_reader_pdf_success",
            lambda: document_reader("local.pdf"),
            "local.pdf",
            1,
            "local.pdf",
            "Local PDF alpha evidence",
            "file",
            1,
        ),
        ValidationCase(
            "search_document_pdf_query_success",
            lambda: search_document('{"path":"searchable.pdf","query":"beta page","limit":1}'),
            '{"path":"searchable.pdf","query":"beta page","limit":1}',
            1,
            "searchable.pdf (chunk 4)",
            "beta page evidence",
            "file",
            2,
            4,
        ),
        ValidationCase(
            "search_document_pdf_page_success",
            lambda: search_document('{"path":"searchable.pdf","page":2,"limit":1}'),
            '{"path":"searchable.pdf","page":2,"limit":1}',
            1,
            "searchable.pdf (chunk 4)",
            "beta page evidence",
            "file",
            2,
            4,
        ),
        ValidationCase(
            "fetch_url_remote_pdf_success",
            lambda: _fetch_remote_pdf("https://example.com/remote.pdf", remote_bytes),
            "https://example.com/remote.pdf",
            1,
            "remote.pdf",
            "Remote PDF alpha evidence",
            "https",
            1,
        ),
        ValidationCase(
            "fetch_url_remote_pdf_query_success",
            lambda: _fetch_remote_pdf(
                '{"url":"https://example.com/remote-searchable.pdf","query":"pricing page"}',
                remote_searchable_bytes,
            )[:1],
            '{"url":"https://example.com/remote-searchable.pdf","query":"pricing page"}',
            1,
            "remote-searchable.pdf",
            "pricing page evidence",
            "https",
            2,
        ),
        ValidationCase(
            "bad_remote_pdf_returns_empty",
            lambda: _fetch_remote_pdf("https://example.com/bad.pdf", bad_bytes),
            "https://example.com/bad.pdf",
            0,
        ),
        ValidationCase(
            "empty_remote_pdf_returns_empty",
            lambda: _fetch_remote_pdf("https://example.com/empty.pdf", empty_bytes),
            "https://example.com/empty.pdf",
            0,
        ),
    ]


def _fetch_remote_pdf(query: str, body: bytes) -> list[Evidence]:
    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")

    original_fetch_text = fetch_url_module.fetch_text

    def fake_fetch_text(url: str) -> FetchedPage:
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="application/pdf",
            text=body.decode("latin-1", errors="ignore"),
            body=body,
        )

    fetch_url_module.fetch_text = fake_fetch_text
    try:
        return fetch_url_tool(query, "pdf-validation")
    finally:
        fetch_url_module.fetch_text = original_fetch_text


def _run_case(case: ValidationCase) -> dict[str, Any]:
    try:
        evidence = case.runner()
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
        and item.chunk_index == case.expected_chunk_index
        and urlparse(item.source_url).scheme == case.expected_source_url_scheme
        and item.document_page == case.expected_document_page
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
        "chunk_index": item.chunk_index if item else None,
        "document_page": item.document_page if item else None,
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
    lines = [
        "# PDF Fetch Validation",
        "",
        "| Case | Passed | Evidence | Expected | Title | Source type | Verified | "
        "URL scheme | Chunk | Page | Snippet check | Error |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for case in payload["cases"]:
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in [
                    case["name"],
                    case["passed"],
                    case["evidence_count"],
                    case["expected_evidence_count"],
                    case["title"],
                    case["source_type"],
                    case["verified"],
                    case["source_url_scheme"],
                    case["chunk_index"],
                    case["document_page"],
                    case["snippet_contains"],
                    case["error"],
                ]
            )
            + " |"
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
            + " | ".join(
                _markdown_cell(value)
                for value in [
                    summary["case_count"],
                    summary["passed_count"],
                    summary["failed_count"],
                    summary["all_passed"],
                    summary["total_evidence_count"],
                ]
            )
            + " |",
            "",
        ]
    )
    return "\n".join(lines)


def _markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value).replace("\n", " ").replace("|", r"\|")


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = ValidationArgumentParser(
        description="Validate PDF fetch and retrieval evidence.",
        stderr=stderr,
    )
    parser.add_argument("--markdown", action="store_true", help="write Markdown instead of JSON")
    try:
        args = parser.parse_args(argv)
        payload = run_validation()
        output = (
            format_markdown(payload)
            if args.markdown
            else json.dumps(payload, indent=2, sort_keys=True) + "\n"
        )
        stdout.write(output)
    except SystemExit as exc:
        return int(exc.code)
    except OSError:
        stderr.write(f"{SCRIPT_ERROR_PREFIX}: failed to write output\n")
        return 2
    except Exception:
        stderr.write(f"{SCRIPT_ERROR_PREFIX}: unexpected error\n")
        return 2
    return 0 if payload["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
