# Run With LLM Log Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/run_with_llm_log.py`, a safe script wrapper that runs research, prints Markdown, and writes a per-run safe LLM metadata JSON log.

**Architecture:** Reuse the proven `scripts/run_research.py` input/preset/output helpers where possible, but keep log payload, slug/path generation, and write behavior as focused pure functions in the new script. Tests inject fake workflow and clock functions, so no real network, search provider, or LLM is used.

**Tech Stack:** Python standard library, existing `insight_graph.cli` helpers, existing `insight_graph.graph.run_research`, pytest, Ruff.

---

## File Structure

- Create `scripts/run_with_llm_log.py`: parser, query reading, preset application, safe log payload creation, log filename generation, log writing, Markdown stdout output, safe exit codes.
- Create `tests/test_run_with_llm_log_script.py`: offline unit tests for query handling, log schema, file naming/collisions, safe errors, preset behavior, and output behavior.
- Modify `README.md`: mark `scripts/run_with_llm_log.py` as current and document usage.

The script must not record prompts, completions, raw LLM responses, headers, API keys, request bodies, raw provider errors, full report text, full findings, full competitive matrix, or evidence pools.

---

### Task 1: Log Payload And File Naming

**Files:**
- Create: `scripts/run_with_llm_log.py`
- Create: `tests/test_run_with_llm_log_script.py`

- [ ] **Step 1: Write failing tests for log payload and path generation**

Create `tests/test_run_with_llm_log_script.py` with this content:

```python
from datetime import datetime, timezone

import scripts.run_with_llm_log as llm_log_script
from insight_graph.state import (
    CompetitiveMatrixRow,
    Critique,
    Finding,
    GraphState,
    LLMCallRecord,
    ToolCallRecord,
)


FIXED_NOW = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)


def make_state(query: str) -> GraphState:
    return GraphState(
        user_request=query,
        report_markdown="# InsightGraph Research Report\n\n## References\n",
        findings=[
            Finding(
                title="Sensitive finding title should not be logged",
                summary="Sensitive finding summary should not be logged",
                evidence_ids=["evidence-1"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Cursor",
                positioning="Sensitive matrix positioning should not be logged",
                strengths=["Sensitive matrix strength should not be logged"],
                evidence_ids=["evidence-1"],
            )
        ],
        critique=Critique(passed=True, reason="Citations present."),
        tool_call_log=[
            ToolCallRecord(
                subtask_id="collect",
                tool_name="mock_search",
                query=query,
                evidence_count=3,
                filtered_count=0,
                success=True,
            )
        ],
        llm_call_log=[
            LLMCallRecord(
                stage="reporter",
                provider="llm",
                model="relay-model",
                wire_api="responses",
                success=True,
                duration_ms=12,
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
            )
        ],
        iterations=2,
    )


def test_build_log_payload_contains_only_safe_metadata():
    state = make_state("Compare Cursor")

    payload = llm_log_script.build_log_payload(state, preset="offline")

    assert payload == {
        "query": "Compare Cursor",
        "preset": "offline",
        "report_markdown_length": len(state.report_markdown or ""),
        "finding_count": 1,
        "competitive_matrix_row_count": 1,
        "tool_call_log": [state.tool_call_log[0].model_dump(mode="json")],
        "llm_call_log": [state.llm_call_log[0].model_dump(mode="json")],
        "iterations": 2,
    }


def test_build_log_payload_omits_sensitive_fields():
    state = make_state("Compare Cursor")

    payload_text = str(llm_log_script.build_log_payload(state, preset="offline")).lower()

    assert "report_markdown" not in payload_text
    assert "sensitive finding" not in payload_text
    assert "sensitive matrix" not in payload_text
    assert "evidence_pool" not in payload_text
    assert "prompt" not in payload_text
    assert "completion" not in payload_text
    assert "api_key" not in payload_text


def test_slugify_query_limits_and_normalizes_filename_component():
    slug = llm_log_script.slugify_query("  Cursor + OpenCode / GitHub Copilot!!!  ")

    assert slug == "cursor-opencode-github-copilot"
    assert len(llm_log_script.slugify_query("a" * 200)) == 60
    assert llm_log_script.slugify_query("!!!") == "research"


def test_build_log_path_uses_utc_timestamp_slug_and_collision_suffix(tmp_path):
    first = llm_log_script.build_log_path(
        log_dir=tmp_path,
        query="Compare Cursor, OpenCode, and GitHub Copilot",
        now=FIXED_NOW,
    )
    first.write_text("existing", encoding="utf-8")
    second = llm_log_script.build_log_path(
        log_dir=tmp_path,
        query="Compare Cursor, OpenCode, and GitHub Copilot",
        now=FIXED_NOW,
    )

    assert first.name == "20260426T120000Z-compare-cursor-opencode-and-github-copilot.json"
    assert second.name == "20260426T120000Z-compare-cursor-opencode-and-github-copilot-2.json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_run_with_llm_log_script.py -q
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'scripts.run_with_llm_log'` or `ImportError` because the script does not exist yet.

- [ ] **Step 3: Implement log payload and path helpers**

Create `scripts/run_with_llm_log.py` with this content:

```python
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from insight_graph.state import GraphState


MAX_SLUG_LENGTH = 60


def build_log_payload(state: GraphState, *, preset: str) -> dict[str, Any]:
    return {
        "query": state.user_request,
        "preset": preset,
        "report_markdown_length": len(state.report_markdown or ""),
        "finding_count": len(state.findings),
        "competitive_matrix_row_count": len(state.competitive_matrix),
        "tool_call_log": [record.model_dump(mode="json") for record in state.tool_call_log],
        "llm_call_log": [record.model_dump(mode="json") for record in state.llm_call_log],
        "iterations": state.iterations,
    }


def slugify_query(query: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:MAX_SLUG_LENGTH]
    slug = slug.strip("-")
    return slug or "research"


def build_log_path(*, log_dir: Path, query: str, now: datetime) -> Path:
    timestamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"{timestamp}-{slugify_query(query)}"
    candidate = log_dir / f"{base_name}.json"
    suffix = 2
    while candidate.exists():
        candidate = log_dir / f"{base_name}-{suffix}.json"
        suffix += 1
    return candidate
```

- [ ] **Step 4: Run tests and lint for Task 1**

Run:

```powershell
python -m pytest tests/test_run_with_llm_log_script.py -q
python -m ruff check scripts/run_with_llm_log.py tests/test_run_with_llm_log_script.py
```

Expected: all Task 1 tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add scripts/run_with_llm_log.py tests/test_run_with_llm_log_script.py
git commit -m "feat: add llm log payload helpers"
```

---

### Task 2: CLI, Log Writing, And Safe Errors

**Files:**
- Modify: `scripts/run_with_llm_log.py`
- Modify: `tests/test_run_with_llm_log_script.py`

- [ ] **Step 1: Add failing CLI and error tests**

Append this content to `tests/test_run_with_llm_log_script.py`:

```python
import io
import json
import os


class BadStdout:
    def write(self, value: str) -> int:
        raise OSError("cannot write")


class BadStdin:
    def read(self) -> str:
        raise OSError("cannot read")


def clear_live_defaults(monkeypatch) -> None:
    for name in llm_log_script.LIVE_LLM_PRESET_DEFAULTS:
        monkeypatch.delenv(name, raising=False)


def fixed_now() -> datetime:
    return FIXED_NOW


def test_main_runs_query_writes_markdown_and_log_file(tmp_path):
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_state(query)

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["Compare Cursor", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fake_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 0
    assert observed_queries == ["Compare Cursor"]
    assert stderr.getvalue() == ""
    assert stdout.getvalue().startswith("# InsightGraph Research Report")
    assert "LLM log written to:" in stdout.getvalue()
    log_files = list(tmp_path.glob("*.json"))
    assert [path.name for path in log_files] == ["20260426T120000Z-compare-cursor.json"]
    payload = json.loads(log_files[0].read_text(encoding="utf-8"))
    assert payload["query"] == "Compare Cursor"
    assert payload["preset"] == "offline"
    assert payload["llm_call_log"][0]["wire_api"] == "responses"


def test_main_reads_query_from_stdin_dash(tmp_path):
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_state(query)

    exit_code = llm_log_script.main(
        ["-", "--log-dir", str(tmp_path)],
        stdin=io.StringIO("  Compare from stdin\n"),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 0
    assert observed_queries == ["Compare from stdin"]


def test_main_rejects_empty_query_without_running_workflow(tmp_path):
    def fail_run_research(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["  ", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Research query must not be empty.\n"
    assert list(tmp_path.glob("*.json")) == []


def test_main_offline_preset_does_not_apply_live_defaults(monkeypatch, tmp_path):
    clear_live_defaults(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in llm_log_script.LIVE_LLM_PRESET_DEFAULTS}
        )
        return make_state(query)

    exit_code = llm_log_script.main(
        ["Compare", "--preset", "offline", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 0
    assert observed_env == {name: None for name in llm_log_script.LIVE_LLM_PRESET_DEFAULTS}


def test_main_live_llm_preset_applies_defaults(monkeypatch, tmp_path):
    clear_live_defaults(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in llm_log_script.LIVE_LLM_PRESET_DEFAULTS}
        )
        return make_state(query)

    exit_code = llm_log_script.main(
        ["Compare", "--preset", "live-llm", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 0
    assert observed_env == llm_log_script.LIVE_LLM_PRESET_DEFAULTS


def test_main_workflow_exception_returns_one_without_log_or_raw_error(tmp_path):
    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider details")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["Compare", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Research workflow failed.\n"
    assert "secret provider details" not in stderr.getvalue()
    assert list(tmp_path.glob("*.json")) == []


def test_main_log_dir_as_file_returns_two_without_running_workflow(tmp_path):
    log_path = tmp_path / "llm_logs"
    log_path.write_text("not a directory", encoding="utf-8")

    def fail_run_research(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["Compare", "--log-dir", str(log_path)],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Failed to prepare LLM log directory.\n"


def test_main_stdin_read_failure_returns_two_without_workflow(tmp_path):
    def fail_run_research(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["-", "--log-dir", str(tmp_path)],
        stdin=BadStdin(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Failed to read query.\n"


def test_main_stdout_write_failure_returns_two_after_log_written(tmp_path):
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["Compare", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=BadStdout(),
        stderr=stderr,
        run_research_func=make_state,
        now_func=fixed_now,
    )

    assert exit_code == 2
    assert stderr.getvalue() == "Failed to write output.\n"
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_main_unknown_option_returns_two_without_traceback():
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["Compare", "--unknown"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=make_state,
        now_func=fixed_now,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "usage:" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_run_with_llm_log_script.py -q
```

Expected: FAIL with `AttributeError` or `ImportError` because CLI functions do not exist yet.

- [ ] **Step 3: Implement CLI and log writing**

Replace `scripts/run_with_llm_log.py` with this content:

```python
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from insight_graph.cli import (
    LIVE_LLM_PRESET_DEFAULTS,
    ResearchPreset,
    _apply_research_preset,
    _configure_output_encoding,
)
from insight_graph.graph import run_research
from insight_graph.state import GraphState


MAX_SLUG_LENGTH = 60

__all__ = ["LIVE_LLM_PRESET_DEFAULTS", "build_log_payload", "build_log_path", "main", "slugify_query"]


class LLMLogArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, stdout: TextIO, stderr: TextIO, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stdout = stdout
        self._stderr = stderr

    def print_help(self, file: TextIO | None = None) -> None:
        super().print_help(file or self._stdout)

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message:
            self._stderr.write(message)
        raise SystemExit(status)

    def error(self, message: str) -> None:
        self.print_usage(self._stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


def build_log_payload(state: GraphState, *, preset: str) -> dict[str, Any]:
    return {
        "query": state.user_request,
        "preset": preset,
        "report_markdown_length": len(state.report_markdown or ""),
        "finding_count": len(state.findings),
        "competitive_matrix_row_count": len(state.competitive_matrix),
        "tool_call_log": [record.model_dump(mode="json") for record in state.tool_call_log],
        "llm_call_log": [record.model_dump(mode="json") for record in state.llm_call_log],
        "iterations": state.iterations,
    }


def slugify_query(query: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:MAX_SLUG_LENGTH]
    slug = slug.strip("-")
    return slug or "research"


def build_log_path(*, log_dir: Path, query: str, now: datetime) -> Path:
    timestamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"{timestamp}-{slugify_query(query)}"
    candidate = log_dir / f"{base_name}.json"
    suffix = 2
    while candidate.exists():
        candidate = log_dir / f"{base_name}-{suffix}.json"
        suffix += 1
    return candidate


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    run_research_func: Callable[[str], GraphState] = run_research,
    now_func: Callable[[], datetime] | None = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    now_func = now_func or (lambda: datetime.now(timezone.utc))
    _configure_output_encoding(stdout=stdout, stderr=stderr)

    parser = LLMLogArgumentParser(
        description="Run InsightGraph research and write safe LLM metadata logs.",
        stdout=stdout,
        stderr=stderr,
    )
    parser.add_argument("query", help="Research query, or '-' to read from stdin.")
    parser.add_argument(
        "--preset",
        choices=[preset.value for preset in ResearchPreset],
        default=ResearchPreset.offline.value,
        help="Runtime preset: offline or live-llm.",
    )
    parser.add_argument(
        "--log-dir",
        default="llm_logs",
        help="Directory where the safe LLM metadata JSON log will be written.",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        query = _read_query(args.query, stdin)
    except OSError:
        stderr.write("Failed to read query.\n")
        return 2

    if not query:
        stderr.write("Research query must not be empty.\n")
        return 2

    log_dir = Path(args.log_dir)
    if not _prepare_log_dir(log_dir):
        stderr.write("Failed to prepare LLM log directory.\n")
        return 2

    _apply_research_preset(ResearchPreset(args.preset))

    try:
        state = run_research_func(query)
    except Exception:
        stderr.write("Research workflow failed.\n")
        return 1

    log_path = build_log_path(log_dir=log_dir, query=query, now=now_func())
    try:
        _write_log(log_path, build_log_payload(state, preset=args.preset))
    except OSError:
        stderr.write("Failed to write LLM log.\n")
        return 2

    try:
        stdout.write(_format_stdout(state.report_markdown or "", log_path))
    except (OSError, UnicodeError):
        stderr.write("Failed to write output.\n")
        return 2

    return 0


def _read_query(query_arg: str, stdin: TextIO) -> str:
    if query_arg == "-":
        return stdin.read().strip()
    return query_arg.strip()


def _prepare_log_dir(log_dir: Path) -> bool:
    try:
        if log_dir.exists() and not log_dir.is_dir():
            return False
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return True


def _write_log(log_path: Path, payload: dict[str, Any]) -> None:
    with log_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _format_stdout(report_markdown: str, log_path: Path) -> str:
    report = report_markdown.rstrip("\r\n") + "\n"
    return f"{report}\nLLM log written to: {log_path}\n"


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and lint for Task 2**

Run:

```powershell
python -m pytest tests/test_run_with_llm_log_script.py -q
python -m ruff check scripts/run_with_llm_log.py tests/test_run_with_llm_log_script.py
```

Expected: all Task 2 tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add scripts/run_with_llm_log.py tests/test_run_with_llm_log_script.py
git commit -m "feat: add run with llm log script"
```

---

### Task 3: README Documentation

**Files:**
- Modify: `README.md:586-634`

- [ ] **Step 1: Run pre-documentation tests**

Run:

```powershell
python -m pytest tests/test_run_with_llm_log_script.py tests/test_run_research_script.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Update script status and usage docs**

In `README.md`, replace the `scripts/run_with_llm_log.py` row in the `## 脚本状态` table with:

```markdown
| `scripts/run_with_llm_log.py` | 当前可用 | 运行 research workflow，stdout 输出 Markdown，并将安全 LLM metadata 写入 `llm_logs/`；不记录 prompt、completion、raw response 或 API key |
```

After the current run research usage section, add this section. Use normal fenced `bash` blocks in the README:

~~~markdown
当前 run with LLM log 用法：

```bash
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_with_llm_log.py - < query.txt
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot" --log-dir tmp_llm_logs
```

该脚本会把本次运行的安全 LLM metadata 写入 JSON 文件。日志包含 `tool_call_log`、`llm_call_log`、summary counts 和 iterations；不包含完整报告、完整 findings、evidence pool、prompt、completion、raw response、headers、request body 或 API key。
~~~

- [ ] **Step 3: Run documentation-adjacent tests**

Run:

```powershell
python -m pytest tests/test_run_with_llm_log_script.py tests/test_run_research_script.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Commit Task 3**

Run:

```powershell
git add README.md
git commit -m "docs: document run with llm log script"
```

---

### Task 4: Final Verification And Smoke

**Files:**
- Verify only unless a failure requires a targeted fix.

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
python -m pytest tests/test_run_with_llm_log_script.py tests/test_run_research_script.py -q
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

- [ ] **Step 4: Run smoke with temporary log directory**

Run:

```powershell
$logDir = "tmp_llm_logs_smoke"; if (Test-Path $logDir) { Remove-Item -Recurse -Force $logDir }; python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot" --log-dir $logDir
```

Expected stdout contains:

```text
# InsightGraph Research Report
LLM log written to:
```

- [ ] **Step 5: Inspect smoke log contents**

Run:

```powershell
$logFile = Get-ChildItem "tmp_llm_logs_smoke" -Filter "*.json" | Select-Object -First 1; Get-Content $logFile.FullName
```

Expected log JSON contains:

```text
"llm_call_log"
"tool_call_log"
```

Expected log JSON does not contain:

```text
prompt
completion
api_key
```

- [ ] **Step 6: Remove smoke log directory**

Run:

```powershell
Remove-Item -Recurse -Force "tmp_llm_logs_smoke"
```

- [ ] **Step 7: Commit any verification fixes**

If Steps 1-6 required fixes, commit only the targeted fixes:

```powershell
git add scripts/run_with_llm_log.py tests/test_run_with_llm_log_script.py README.md
git commit -m "fix: harden run with llm log script"
```

If no files changed, do not create an empty commit.

---

## Self-Review

- Spec coverage: Tasks cover query/stdin input, preset behavior, log directory behavior, filename slug/collision, safe log schema, sensitive-field exclusions, safe exit codes, README docs, focused/full tests, lint, and smoke.
- Placeholder scan: No placeholders remain; every code-changing step includes concrete code or exact README text.
- Type consistency: The plan consistently uses `build_log_payload(state, preset)`, `slugify_query(query)`, `build_log_path(log_dir, query, now)`, and `main(argv, stdin, stdout, stderr, run_research_func, now_func)`.
