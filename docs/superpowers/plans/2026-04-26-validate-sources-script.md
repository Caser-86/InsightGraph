# Validate Sources Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline `scripts/validate_sources.py` script that validates Markdown report citations, References entries, URL shape, and duplicate references.

**Architecture:** Keep this as a focused script with pure validation functions plus a small CLI wrapper. Tests call pure functions for parser behavior and `main()` for I/O, exit codes, and output modes.

**Tech Stack:** Python standard library only, pytest, Ruff, existing src-layout project commands.

---

## File Structure

- Create `scripts/validate_sources.py`: parser, validator, JSON output, Markdown output, and `main(argv, stdin, stdout, stderr)`.
- Create `tests/test_validate_sources.py`: offline unit tests for parser behavior, issue payloads, CLI exit codes, stdin, missing file handling, and Markdown formatting.
- Modify `README.md`: mark `scripts/validate_sources.py` as current and document usage.

The script should not import `insight_graph`, should not access the network, and should not mutate environment variables.

---

### Task 1: Core Parser And Validation Payload

**Files:**
- Create: `scripts/validate_sources.py`
- Create: `tests/test_validate_sources.py`

- [ ] **Step 1: Write failing tests for parser and issue payloads**

Create `tests/test_validate_sources.py` with this content:

```python
from scripts.validate_sources import validate_report


VALID_REPORT = """# Report

Cursor pricing is documented publicly [1]. Copilot docs describe product behavior [2].

## References

[1] Cursor Pricing. https://cursor.com/pricing
[2] GitHub Copilot Docs. https://docs.github.com/en/copilot
"""


def issue_types(payload: dict) -> list[str]:
    return [issue["type"] for issue in payload["issues"]]


def test_validate_report_accepts_valid_references():
    payload = validate_report(VALID_REPORT)

    assert payload == {
        "ok": True,
        "citation_count": 2,
        "reference_count": 2,
        "issues": [],
    }


def test_validate_report_reports_missing_references_section():
    payload = validate_report("# Report\n\nThis report cites one source [1].\n")

    assert payload["ok"] is False
    assert payload["citation_count"] == 1
    assert payload["reference_count"] == 0
    assert payload["issues"] == [
        {
            "type": "missing_references_section",
            "reference": None,
            "message": "Report has no References or Sources section.",
        }
    ]


def test_validate_report_reports_missing_reference_for_citation():
    payload = validate_report(
        """# Report

The report cites a missing source [2].

## References

[1] Existing source. https://example.com/source
"""
    )

    assert issue_types(payload) == ["missing_reference", "unused_reference"]
    assert payload["issues"][0] == {
        "type": "missing_reference",
        "reference": 2,
        "message": "Citation [2] has no matching reference.",
    }


def test_validate_report_reports_unused_reference():
    payload = validate_report(
        """# Report

The report cites one source [1].

## References

[1] Used source. https://example.com/used
[2] Unused source. https://example.com/unused
"""
    )

    assert issue_types(payload) == ["unused_reference"]
    assert payload["issues"][0] == {
        "type": "unused_reference",
        "reference": 2,
        "message": "Reference [2] is not cited in the report body.",
    }


def test_validate_report_reports_invalid_reference_url():
    payload = validate_report(
        """# Report

The report cites one source [1].

## References

[1] Bad URL source. ftp://example.com/source
"""
    )

    assert issue_types(payload) == ["invalid_reference_url"]
    assert payload["issues"][0] == {
        "type": "invalid_reference_url",
        "reference": 1,
        "message": "Reference [1] URL must start with http:// or https://.",
    }


def test_validate_report_reports_duplicate_reference_number():
    payload = validate_report(
        """# Report

The report cites one source [1].

## References

[1] First source. https://example.com/first
[1] Duplicate source. https://example.com/duplicate
"""
    )

    assert issue_types(payload) == ["duplicate_reference"]
    assert payload["issues"][0] == {
        "type": "duplicate_reference",
        "reference": 1,
        "message": "Reference [1] appears more than once.",
    }


def test_validate_report_ignores_citations_inside_references_section():
    payload = validate_report(
        """# Report

The report cites one source [1].

## References

[1] Source title mentioning [2]. https://example.com/source
"""
    )

    assert payload["ok"] is True
    assert payload["citation_count"] == 1
    assert payload["reference_count"] == 1
    assert payload["issues"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_validate_sources.py -q
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'scripts.validate_sources'` or `ImportError` because the script does not exist yet.

- [ ] **Step 3: Implement the core validator**

Create `scripts/validate_sources.py` with this content:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*#*\s*$")
CITATION_RE = re.compile(r"\[(\d+)\]")
REFERENCE_RE = re.compile(r"^\[(\d+)\]\s+(.+?)\s*$")


@dataclass(frozen=True)
class ReferenceSection:
    start_line: int
    end_line: int
    level: int


def validate_report(markdown: str) -> dict[str, Any]:
    lines = markdown.splitlines()
    section = _find_reference_section(lines)
    reference_lines = _reference_lines(lines, section)
    body = _body_without_reference_section(lines, section)
    citations = _extract_citations(body)
    references, duplicate_references, invalid_url_references = _parse_references(reference_lines)

    issues: list[dict[str, Any]] = []
    if section is None:
        issues.append(
            {
                "type": "missing_references_section",
                "reference": None,
                "message": "Report has no References or Sources section.",
            }
        )

    for reference in sorted(citations - set(references)):
        issues.append(
            {
                "type": "missing_reference",
                "reference": reference,
                "message": f"Citation [{reference}] has no matching reference.",
            }
        )

    for reference in sorted(set(references) - citations):
        issues.append(
            {
                "type": "unused_reference",
                "reference": reference,
                "message": f"Reference [{reference}] is not cited in the report body.",
            }
        )

    for reference in sorted(invalid_url_references):
        issues.append(
            {
                "type": "invalid_reference_url",
                "reference": reference,
                "message": f"Reference [{reference}] URL must start with http:// or https://.",
            }
        )

    for reference in sorted(duplicate_references):
        issues.append(
            {
                "type": "duplicate_reference",
                "reference": reference,
                "message": f"Reference [{reference}] appears more than once.",
            }
        )

    return {
        "ok": not issues,
        "citation_count": len(citations),
        "reference_count": len(references),
        "issues": issues,
    }


def _find_reference_section(lines: list[str]) -> ReferenceSection | None:
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        title = match.group(2).strip().lower()
        if title not in {"references", "sources"}:
            continue

        level = len(match.group(1))
        end_line = len(lines)
        for next_index in range(index + 1, len(lines)):
            next_match = HEADING_RE.match(lines[next_index])
            if next_match and len(next_match.group(1)) <= level:
                end_line = next_index
                break
        return ReferenceSection(start_line=index, end_line=end_line, level=level)
    return None


def _reference_lines(lines: list[str], section: ReferenceSection | None) -> list[str]:
    if section is None:
        return []
    return lines[section.start_line + 1 : section.end_line]


def _body_without_reference_section(lines: list[str], section: ReferenceSection | None) -> str:
    if section is None:
        return "\n".join(lines)
    return "\n".join(lines[: section.start_line] + lines[section.end_line :])


def _extract_citations(markdown: str) -> set[int]:
    return {int(match.group(1)) for match in CITATION_RE.finditer(markdown) if int(match.group(1)) > 0}


def _parse_references(lines: list[str]) -> tuple[dict[int, str], set[int], set[int]]:
    references: dict[int, str] = {}
    duplicate_references: set[int] = set()
    invalid_url_references: set[int] = set()

    for line in lines:
        match = REFERENCE_RE.match(line.strip())
        if not match:
            continue

        reference = int(match.group(1))
        if reference <= 0:
            continue

        text = match.group(2).strip()
        url = text.split()[-1] if text.split() else ""
        if not (url.startswith("http://") or url.startswith("https://")):
            invalid_url_references.add(reference)

        if reference in references:
            duplicate_references.add(reference)
            continue
        references[reference] = url

    return references, duplicate_references, invalid_url_references
```

- [ ] **Step 4: Run tests to verify Task 1 passes**

Run:

```powershell
python -m pytest tests/test_validate_sources.py -q
```

Expected: `7 passed`.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add scripts/validate_sources.py tests/test_validate_sources.py
git commit -m "feat: add source validation payload"
```

---

### Task 2: JSON CLI, Stdin, And Error Exit Codes

**Files:**
- Modify: `scripts/validate_sources.py`
- Modify: `tests/test_validate_sources.py`

- [ ] **Step 1: Add failing CLI tests**

Append these tests to `tests/test_validate_sources.py`:

```python
import io
import json

from scripts.validate_sources import main


def test_main_reads_file_and_writes_json(tmp_path):
    report_path = tmp_path / "report.md"
    report_path.write_text(VALID_REPORT, encoding="utf-8")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main([str(report_path)], stdin=io.StringIO(), stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["issues"] == []


def test_main_reads_stdin_when_path_is_dash():
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(["-"], stdin=io.StringIO(VALID_REPORT), stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue())["ok"] is True


def test_main_returns_one_when_issues_exist():
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(["-"], stdin=io.StringIO("# Report\n\nMissing refs [1].\n"), stdout=stdout, stderr=stderr)

    assert exit_code == 1
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is False
    assert payload["issues"][0]["type"] == "missing_references_section"


def test_main_returns_two_for_missing_file_without_traceback(tmp_path):
    missing_path = tmp_path / "missing.md"
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main([str(missing_path)], stdin=io.StringIO(), stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "Failed to read input" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()
```

- [ ] **Step 2: Run tests to verify CLI tests fail**

Run:

```powershell
python -m pytest tests/test_validate_sources.py -q
```

Expected: FAIL with `ImportError: cannot import name 'main'`.

- [ ] **Step 3: Add CLI and JSON output**

Update `scripts/validate_sources.py` by adding these imports near the top:

```python
import argparse
import json
import sys
from pathlib import Path
from typing import TextIO
```

Then append these functions near the bottom of the file:

```python
def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    parser = argparse.ArgumentParser(description="Validate Markdown report citations and references.")
    parser.add_argument("path", help="Markdown report path, or '-' to read from stdin.")
    args = parser.parse_args(argv)

    try:
        markdown = _read_input(args.path, stdin)
    except OSError as exc:
        stderr.write(f"Failed to read input: {exc}\n")
        return 2

    payload = validate_report(markdown)
    json.dump(payload, stdout, indent=2, ensure_ascii=False)
    stdout.write("\n")
    return 0 if payload["ok"] else 1


def _read_input(path: str, stdin: TextIO) -> str:
    if path == "-":
        return stdin.read()
    return Path(path).read_text(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify Task 2 passes**

Run:

```powershell
python -m pytest tests/test_validate_sources.py -q
```

Expected: `11 passed`.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add scripts/validate_sources.py tests/test_validate_sources.py
git commit -m "feat: add source validator cli"
```

---

### Task 3: Markdown Output Mode

**Files:**
- Modify: `scripts/validate_sources.py`
- Modify: `tests/test_validate_sources.py`

- [ ] **Step 1: Add failing Markdown output tests**

Append these tests to `tests/test_validate_sources.py`:

```python
from scripts.validate_sources import format_markdown


def test_format_markdown_writes_summary_without_issues():
    payload = validate_report(VALID_REPORT)

    output = format_markdown(payload)

    assert "# Source Validation" in output
    assert "| OK | Citations | References | Issues |" in output
    assert "| true | 2 | 2 | 0 |" in output
    assert "## Issues" not in output


def test_format_markdown_writes_issue_table_with_escaped_cells():
    payload = {
        "ok": False,
        "citation_count": 1,
        "reference_count": 0,
        "issues": [
            {
                "type": "missing_reference",
                "reference": 1,
                "message": "Line one | line two\nline three",
            }
        ],
    }

    output = format_markdown(payload)

    assert "## Issues" in output
    assert "| missing_reference | 1 | Line one \\| line two line three |" in output


def test_main_writes_markdown_when_flag_is_present():
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(["-", "--markdown"], stdin=io.StringIO(VALID_REPORT), stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert stdout.getvalue().startswith("# Source Validation")
    assert "| true | 2 | 2 | 0 |" in stdout.getvalue()
```

- [ ] **Step 2: Run tests to verify Markdown tests fail**

Run:

```powershell
python -m pytest tests/test_validate_sources.py -q
```

Expected: FAIL with `ImportError: cannot import name 'format_markdown'`.

- [ ] **Step 3: Add Markdown formatter and CLI flag**

Append these functions above `main()` in `scripts/validate_sources.py`:

```python
def format_markdown(payload: dict[str, Any]) -> str:
    ok = str(payload["ok"]).lower()
    issue_count = len(payload["issues"])
    lines = [
        "# Source Validation",
        "",
        "| OK | Citations | References | Issues |",
        "| --- | ---: | ---: | ---: |",
        f"| {ok} | {payload['citation_count']} | {payload['reference_count']} | {issue_count} |",
    ]

    if payload["issues"]:
        lines.extend(
            [
                "",
                "## Issues",
                "",
                "| Type | Reference | Message |",
                "| --- | ---: | --- |",
            ]
        )
        for issue in payload["issues"]:
            reference = "" if issue["reference"] is None else str(issue["reference"])
            lines.append(
                "| "
                f"{_escape_markdown_table_cell(issue['type'])} | "
                f"{reference} | "
                f"{_escape_markdown_table_cell(issue['message'])} |"
            )

    return "\n".join(lines) + "\n"


def _escape_markdown_table_cell(value: object) -> str:
    return str(value).replace("\n", " ").replace("|", r"\|")
```

Then update `main()` to add the flag and choose output format:

```python
def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    parser = argparse.ArgumentParser(description="Validate Markdown report citations and references.")
    parser.add_argument("path", help="Markdown report path, or '-' to read from stdin.")
    parser.add_argument("--markdown", action="store_true", help="Write GitHub-flavored Markdown output.")
    args = parser.parse_args(argv)

    try:
        markdown = _read_input(args.path, stdin)
    except OSError as exc:
        stderr.write(f"Failed to read input: {exc}\n")
        return 2

    payload = validate_report(markdown)
    if args.markdown:
        stdout.write(format_markdown(payload))
    else:
        json.dump(payload, stdout, indent=2, ensure_ascii=False)
        stdout.write("\n")
    return 0 if payload["ok"] else 1
```

- [ ] **Step 4: Run tests to verify Task 3 passes**

Run:

```powershell
python -m pytest tests/test_validate_sources.py -q
```

Expected: `14 passed`.

- [ ] **Step 5: Commit Task 3**

Run:

```powershell
git add scripts/validate_sources.py tests/test_validate_sources.py
git commit -m "feat: format source validation output"
```

---

### Task 4: README Documentation

**Files:**
- Modify: `README.md:586-603`

- [ ] **Step 1: Run pre-documentation tests**

Run:

```powershell
python -m pytest tests/test_validate_sources.py -q
```

Expected: current source validator tests still pass before documentation changes.

- [ ] **Step 2: Update script status and usage docs**

In `README.md`, replace the `scripts/validate_sources.py` row at line 592 with:

```markdown
| `scripts/validate_sources.py` | 当前可用 | 离线校验 Markdown 报告 citation 与 References；支持文件路径或 stdin `-`，默认 JSON 输出，`--markdown` 输出表格；不联网校验 URL 可访问性 |
```

Then replace the paragraph `当前 benchmark 用法：` and its following command block with this content. Use normal fenced `bash` blocks in the README:

~~~markdown
当前 benchmark 用法：

```bash
python scripts/benchmark_research.py
python scripts/benchmark_research.py --markdown
```

该脚本会在进程内清理会改变默认工具/LLM 行为的 opt-in 环境变量，确保 benchmark 使用 offline deterministic workflow。

当前 source validator 用法：

```bash
python scripts/validate_sources.py report.md
python scripts/validate_sources.py - < report.md
python scripts/validate_sources.py report.md --markdown
```

该脚本只做离线结构校验，不请求 URL，也不验证网页是否可访问。
~~~

- [ ] **Step 3: Run documentation-adjacent tests**

Run:

```powershell
python -m pytest tests/test_validate_sources.py tests/test_benchmark_research.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Commit Task 4**

Run:

```powershell
git add README.md
git commit -m "docs: document source validator script"
```

---

### Task 5: Final Verification And Smoke

**Files:**
- Verify only unless a failure requires a targeted fix.

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
python -m pytest tests/test_validate_sources.py tests/test_benchmark_research.py -q
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

- [ ] **Step 4: Run JSON smoke with generated deterministic report**

Run:

```powershell
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" | python scripts/validate_sources.py -
```

Expected stdout contains:

```json
"ok": true
```

and:

```json
"issues": []
```

- [ ] **Step 5: Run Markdown smoke with generated deterministic report**

Run:

```powershell
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" | python scripts/validate_sources.py - --markdown
```

Expected stdout contains:

```markdown
# Source Validation
```

and:

```markdown
| true |
```

- [ ] **Step 6: Commit any verification fixes**

If Steps 1-5 required fixes, commit only the targeted fixes:

```powershell
git add scripts/validate_sources.py tests/test_validate_sources.py README.md
git commit -m "fix: harden source validator script"
```

If no files changed, do not create an empty commit.

---

## Self-Review

- Spec coverage: Tasks cover offline Markdown parsing, stdin/file input, JSON output, Markdown output, exit codes, fixed issue types, README, focused/full tests, lint, and smoke.
- Placeholder scan: No placeholders remain; each code-changing step includes concrete code or exact replacement text.
- Type consistency: The plan consistently uses `validate_report(markdown: str) -> dict[str, Any]`, `format_markdown(payload: dict[str, Any]) -> str`, and `main(argv, stdin, stdout, stderr) -> int`.
