# PDF Fetch Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an offline `scripts/validate_pdf_fetch.py` script that validates local PDF retrieval and mocked remote PDF fetch evidence metadata.

**Architecture:** Follow the existing `scripts/validate_document_reader.py` validator pattern: deterministic temp fixtures, injected stdout/stderr, sanitized per-case failures, JSON by default, Markdown with `--markdown`. The script generates PDFs locally, calls `document_reader`, `search_document`, and `fetch_url` with an in-process fake fetcher for remote PDF cases.

**Tech Stack:** Python 3.11+, pytest, pypdf, existing `Evidence`, `FetchedPage`, `document_reader`, `search_document`, and `fetch_url` modules.

---

## File Structure

- Create `scripts/validate_pdf_fetch.py`: owns PDF validation fixture generation, validation cases, output formatting, and CLI entrypoint.
- Create `tests/test_validate_pdf_fetch.py`: covers the new script's case list, metadata checks, summary, Markdown output, parser errors, output failures, cwd restoration, and sanitized exceptions.
- Modify `docs/reference-parity-roadmap.md`: mark Phase 17 implemented and point next phase at PostgreSQL migration layer.
- Modify `CHANGELOG.md`: document the new validator under Unreleased.

---

### Task 1: Validator Test Skeleton

**Files:**
- Create: `tests/test_validate_pdf_fetch.py`
- Create: `scripts/validate_pdf_fetch.py`

- [ ] **Step 1: Add failing tests for fixed cases and summary**

Create `tests/test_validate_pdf_fetch.py` with imports and these tests:

```python
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
```

- [ ] **Step 2: Add minimal placeholder script so import fails only on behavior**

Create `scripts/validate_pdf_fetch.py`:

```python
from __future__ import annotations


def run_validation() -> dict:
    return {"cases": [], "summary": {}}


def format_markdown(payload: dict) -> str:
    del payload
    return ""


def main(argv: list[str] | None = None, *, stdout=None, stderr=None) -> int:
    del argv, stdout, stderr
    return 0
```

- [ ] **Step 3: Run tests to verify RED**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_validate_pdf_fetch.py -q`

Expected: FAIL because case names and summary are empty.

- [ ] **Step 4: Commit test skeleton**

Run: `git add tests/test_validate_pdf_fetch.py scripts/validate_pdf_fetch.py; git commit -m "test: define pdf fetch validator cases"`

---

### Task 2: Implement Offline Validation Cases

**Files:**
- Modify: `scripts/validate_pdf_fetch.py`
- Test: `tests/test_validate_pdf_fetch.py`

- [ ] **Step 1: Replace placeholder with validator implementation**

Implement `scripts/validate_pdf_fetch.py` with:

```python
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
    _write_minimal_pdf(workspace / "local.pdf", "Local PDF alpha evidence.\fLocal PDF beta page evidence.")
    _write_minimal_pdf(workspace / "remote.pdf", "Remote PDF alpha evidence.\fRemote PDF pricing page evidence.")
    (workspace / "bad.pdf").write_bytes(b"%PDF-1.4\nnot a valid pdf")
    (workspace / "empty.pdf").write_bytes(b"")


def _write_minimal_pdf(path: Path, text: str) -> None:
    pages = text.split("\f")
    objects = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = []
    page_objects = []
    for page_index, page_text in enumerate(pages):
        page_obj = 3 + page_index * 2
        content_obj = page_obj + 1
        kids.append(f"{page_obj} 0 R")
        escaped_text = page_text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")
        content = f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET"
        page_objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {3 + len(pages) * 2} 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            )
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
            lambda: search_document('{"path":"local.pdf","query":"beta page","limit":1}'),
            '{"path":"local.pdf","query":"beta page","limit":1}',
            1,
            "local.pdf",
            "beta page evidence",
            "file",
            2,
        ),
        ValidationCase(
            "search_document_pdf_page_success",
            lambda: search_document('{"path":"local.pdf","page":2,"limit":1}'),
            '{"path":"local.pdf","page":2,"limit":1}',
            1,
            "local.pdf",
            "beta page evidence",
            "file",
            2,
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
                '{"url":"https://example.com/remote.pdf","query":"pricing page"}',
                remote_bytes,
            ),
            '{"url":"https://example.com/remote.pdf","query":"pricing page"}',
            1,
            "remote.pdf",
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
    import insight_graph.tools.fetch_url as fetch_url_module

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
        and item.chunk_index == 1
        and urlparse(item.source_url).scheme == case.expected_source_url_scheme
        and item.document_page == case.expected_document_page
        and case.expected_snippet is not None
        and case.expected_snippet in item.snippet
    )


def _case_payload(case: ValidationCase, evidence: list[Evidence], *, passed: bool, error: str | None) -> dict[str, Any]:
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
        "| Case | Passed | Evidence | Expected | Title | Source type | Verified | URL scheme | Chunk | Page | Snippet check | Error |",
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


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = ValidationArgumentParser(description="Validate PDF fetch and retrieval evidence.", stderr=stderr)
    parser.add_argument("--markdown", action="store_true", help="write Markdown instead of JSON")
    try:
        args = parser.parse_args(argv)
        payload = run_validation()
        output = format_markdown(payload) if args.markdown else json.dumps(payload, indent=2, sort_keys=True) + "\n"
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
```

- [ ] **Step 2: Run tests to verify GREEN**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_validate_pdf_fetch.py -q`

Expected: PASS for current tests.

- [ ] **Step 3: Commit implementation**

Run: `git add scripts/validate_pdf_fetch.py tests/test_validate_pdf_fetch.py; git commit -m "feat(scripts): validate pdf fetch evidence"`

---

### Task 3: CLI, Markdown, And Failure Tests

**Files:**
- Modify: `tests/test_validate_pdf_fetch.py`
- Modify: `scripts/validate_pdf_fetch.py` if tests reveal issues

- [ ] **Step 1: Add metadata, Markdown, CLI, cwd, and sanitized failure tests**

Append to `tests/test_validate_pdf_fetch.py`:

```python
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
    assert query_case["title"] == "local.pdf"
    assert query_case["document_page"] == 2
    assert query_case["snippet_contains"] is True

    remote_case = case_by_name(payload, "fetch_url_remote_pdf_success")
    assert remote_case["title"] == "remote.pdf"
    assert remote_case["source_url_scheme"] == "https"
    assert remote_case["document_page"] == 1
    assert remote_case["snippet_contains"] is True

    remote_query_case = case_by_name(payload, "fetch_url_remote_pdf_query_success")
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
    assert "| document_reader_pdf_success | true | 1 | 1 | local.pdf | docs | true | file | 1 | 1 | true |  |" in output
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
```

- [ ] **Step 2: Run tests and fix only observed failures**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_validate_pdf_fetch.py -q`

Expected: PASS. If Markdown newline fails, ensure `format_markdown()` returns a string ending in `\n`.

- [ ] **Step 3: Commit coverage**

Run: `git add scripts/validate_pdf_fetch.py tests/test_validate_pdf_fetch.py; git commit -m "test: cover pdf fetch validator cli"`

---

### Task 4: Docs And Final Verification

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/reference-parity-roadmap.md`

- [ ] **Step 1: Update roadmap and changelog**

In `CHANGELOG.md`, add an Unreleased bullet:

```markdown
- Added offline `scripts/validate_pdf_fetch.py` to validate PDF fetch and retrieval evidence metadata without network access.
```

In `docs/reference-parity-roadmap.md`, change Phase 17 to implemented and set the next phase:

```markdown
17. PDF fetch/retrieval validation script. **Implemented.**
```

At the bottom, set:

```markdown
Phase 18 starts with the PostgreSQL migration layer for checkpoint and memory tables.
```

- [ ] **Step 2: Run focused verification**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_validate_pdf_fetch.py tests/test_validate_document_reader.py tests/test_fetch_url.py tests/test_tools.py -q`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`

Expected: PASS.

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`

Expected: `All checks passed!`

Run: `git diff --check`

Expected: no output.

- [ ] **Step 4: Commit docs**

Run: `git add CHANGELOG.md docs/reference-parity-roadmap.md; git commit -m "docs: document pdf fetch validator"`

---

## Self-Review

- Spec coverage: the plan creates an offline validator, covers local `document_reader`, local `search_document`, mocked remote `fetch_url`, query ranking, page metadata, empty/bad PDF behavior, JSON and Markdown output, and sanitized errors.
- Placeholder scan: no implementation placeholder remains in the plan; all code steps include concrete code.
- Type consistency: all functions used by tests are defined by Task 2; payload keys match assertions and Markdown formatting.
