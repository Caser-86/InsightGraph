# Validate Document Reader Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline `scripts/validate_document_reader.py` script that validates the current TXT/Markdown `document_reader` behavior and its safety failure paths.

**Architecture:** Keep this as a focused validation script with a temporary fixture workspace, pure payload/formatting functions, and a small CLI wrapper. Tests call `run_validation()` for behavior, `format_markdown()` for rendering, and `main()` for CLI/output/error behavior.

**Tech Stack:** Python standard library, existing `insight_graph.tools.document_reader`, pytest, Ruff.

---

## File Structure

- Create `scripts/validate_document_reader.py`: fixture setup, cwd isolation, case execution, JSON output, Markdown output, and `main(argv, stdout, stderr)`.
- Create `tests/test_validate_document_reader.py`: offline tests for all fixed cases, summary counts, cwd restoration, safe errors, output modes, and write failures.
- Modify `README.md`: mark `scripts/validate_document_reader.py` as current and document usage.

The script should not access the network, should not call LLMs, should not run the research workflow, and should not read or modify user files outside its own temporary workspace.

---

### Task 1: Core Validation Payload

**Files:**
- Create: `scripts/validate_document_reader.py`
- Create: `tests/test_validate_document_reader.py`

- [ ] **Step 1: Write failing tests for validation cases and summary**

Create `tests/test_validate_document_reader.py` with this content:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_validate_document_reader.py -q
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'scripts.validate_document_reader'` or `ImportError` because the script does not exist yet.

- [ ] **Step 3: Implement core validation payload**

Create `scripts/validate_document_reader.py` with this content:

```python
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator
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
        ValidationCase("markdown_file_success", "market.md", 1, "market.md", "Markdown market brief"),
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
```

- [ ] **Step 4: Run tests to verify Task 1 passes**

Run:

```powershell
python -m pytest tests/test_validate_document_reader.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add scripts/validate_document_reader.py tests/test_validate_document_reader.py
git commit -m "feat: add document reader validation payload"
```

---

### Task 2: CLI, Markdown Output, And Safe Errors

**Files:**
- Modify: `scripts/validate_document_reader.py`
- Modify: `tests/test_validate_document_reader.py`

- [ ] **Step 1: Add failing CLI, Markdown, and error tests**

Append these tests to `tests/test_validate_document_reader.py`:

```python
import io
import json

from scripts.validate_document_reader import format_markdown, main


class BadStdout:
    def write(self, value: str) -> int:
        raise OSError("cannot write")


def test_run_validation_restores_cwd_after_case_exception():
    original_cwd = os.getcwd()

    def failing_reader(query: str):
        raise RuntimeError("raw reader failure should not leak")

    payload = run_validation(reader=failing_reader)

    assert os.getcwd() == original_cwd
    assert payload["summary"] == {
        "case_count": 10,
        "passed_count": 0,
        "failed_count": 10,
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

    assert output.startswith("# Document Reader Validation")
    assert "| Case | Passed | Evidence | Expected | Title | Source type | Verified | URL scheme | Snippet check | Error |" in output
    assert "| txt_file_success | true | 1 | 1 | notes.txt | docs | true | file | true |  |" in output
    assert "## Summary" in output
    assert "| 10 | 10 | 0 | true | 4 |" in output
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
    assert payload["summary"]["case_count"] == 10


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_validate_document_reader.py -q
```

Expected: FAIL with `ImportError: cannot import name 'format_markdown'` or `ImportError: cannot import name 'main'`.

- [ ] **Step 3: Add CLI, Markdown formatter, and safe output handling**

Update `scripts/validate_document_reader.py` by adding these imports near the top:

```python
import argparse
import json
import sys
from typing import TextIO
```

Add this parser class after constants:

```python
class ValidationArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, stderr: TextIO, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stderr = stderr

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message:
            self._stderr.write(message)
        raise SystemExit(status)


SCRIPT_ERROR_PREFIX = "Document reader validation failed"
```

Append these functions near the bottom of the file:

```python
def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Document Reader Validation",
        "",
        "| Case | Passed | Evidence | Expected | Title | Source type | Verified | URL scheme | Snippet check | Error |",
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
    parser.add_argument("--markdown", action="store_true", help="Write GitHub-flavored Markdown output.")
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
```

- [ ] **Step 4: Run tests to verify Task 2 passes**

Run:

```powershell
python -m pytest tests/test_validate_document_reader.py -q
```

Expected: `12 passed`.

- [ ] **Step 5: Run Ruff for Task 2 files**

Run:

```powershell
python -m ruff check scripts/validate_document_reader.py tests/test_validate_document_reader.py
```

Expected: `All checks passed!`.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add scripts/validate_document_reader.py tests/test_validate_document_reader.py
git commit -m "feat: format document reader validation output"
```

---

### Task 3: README Documentation

**Files:**
- Modify: `README.md:586-615`

- [ ] **Step 1: Run pre-documentation tests**

Run:

```powershell
python -m pytest tests/test_validate_document_reader.py tests/test_validate_sources.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Update script status and usage docs**

In `README.md`, replace the `scripts/validate_document_reader.py` row in the `## 脚本状态` table with:

```markdown
| `scripts/validate_document_reader.py` | 当前可用 | 离线验证当前本地 TXT/Markdown `document_reader` 行为，默认 JSON 输出，`--markdown` 输出表格；PDF/HTML、分页读取与语义检索验证属于后续路线图 |
```

After the source validator usage block, add this section. Use normal fenced `bash` blocks in the README:

~~~markdown
当前 document reader validator 用法：

```bash
python scripts/validate_document_reader.py
python scripts/validate_document_reader.py --markdown
```

该脚本会在临时目录内创建 TXT/Markdown fixtures，并验证 `document_reader` 的成功读取、unsupported/empty/invalid 文件、缺失文件和路径越界返回空结果；不读取用户文件、不访问公网、不调用 LLM。
~~~

- [ ] **Step 3: Run documentation-adjacent tests**

Run:

```powershell
python -m pytest tests/test_validate_document_reader.py tests/test_validate_sources.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Commit Task 3**

Run:

```powershell
git add README.md
git commit -m "docs: document document reader validator script"
```

---

### Task 4: Final Verification And Smoke

**Files:**
- Verify only unless a failure requires a targeted fix.

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
python -m pytest tests/test_validate_document_reader.py tests/test_validate_sources.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
python -m pytest -q
```

Expected: full suite passes with the existing skipped test count unchanged unless another agent added tests.

- [ ] **Step 3: Run lint**

Run:

```powershell
python -m ruff check .
```

Expected: `All checks passed!`.

- [ ] **Step 4: Run JSON smoke**

Run:

```powershell
python scripts/validate_document_reader.py
```

Expected stdout contains:

```json
"all_passed": true
```

and:

```json
"case_count": 10
```

- [ ] **Step 5: Run Markdown smoke**

Run:

```powershell
python scripts/validate_document_reader.py --markdown
```

Expected stdout contains:

```markdown
# Document Reader Validation
```

and:

```markdown
## Summary
```

- [ ] **Step 6: Commit any verification fixes**

If Steps 1-5 required fixes, commit only the targeted fixes:

```powershell
git add scripts/validate_document_reader.py tests/test_validate_document_reader.py README.md
git commit -m "fix: harden document reader validator script"
```

If no files changed, do not create an empty commit.

---

## Self-Review

- Spec coverage: Tasks cover temporary fixtures, all 10 fixed cases, JSON output, Markdown output, exit codes, safe errors, cwd restoration, README documentation, focused/full tests, lint, and smoke.
- Placeholder scan: No placeholders remain; every code-changing step includes concrete code or exact README text.
- Type consistency: The plan consistently uses `run_validation() -> dict[str, Any]`, `format_markdown(payload: dict[str, Any]) -> str`, and `main(argv, stdout, stderr) -> int`.
