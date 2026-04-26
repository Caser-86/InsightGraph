# Run Research Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/run_research.py`, a safe script wrapper that runs InsightGraph research and prints Markdown or CLI-aligned JSON.

**Architecture:** Keep the script thin: parse args, read query, apply the existing CLI preset helper, call `run_research()`, and format output with the existing CLI JSON payload helper. Tests inject fake workflow functions into `main()` so no network, LLM, or search is used.

**Tech Stack:** Python standard library, existing `insight_graph.cli` helpers, existing `insight_graph.graph.run_research`, pytest, Ruff.

---

## File Structure

- Create `scripts/run_research.py`: argparse wrapper, query reading, preset application, Markdown/JSON output, safe exit codes.
- Create `tests/test_run_research_script.py`: offline tests for query handling, output modes, preset behavior, and safe errors.
- Modify `README.md`: mark `scripts/run_research.py` as current and document usage.

The script must not add workflow behavior. It should reuse the current CLI payload helper so `--output-json` stays aligned with CLI and API output.

---

### Task 1: Script Wrapper And JSON Output

**Files:**
- Create: `scripts/run_research.py`
- Create: `tests/test_run_research_script.py`

- [ ] **Step 1: Write failing wrapper tests**

Create `tests/test_run_research_script.py` with this content:

```python
import io
import json
import os

import scripts.run_research as run_research_script
from insight_graph.state import (
    CompetitiveMatrixRow,
    Critique,
    Finding,
    GraphState,
    LLMCallRecord,
    ToolCallRecord,
)


class BadStdout:
    def write(self, value: str) -> int:
        raise OSError("cannot write")


def clear_live_defaults(monkeypatch) -> None:
    for name in run_research_script.LIVE_LLM_PRESET_DEFAULTS:
        monkeypatch.delenv(name, raising=False)


def make_state(query: str) -> GraphState:
    return GraphState(
        user_request=query,
        report_markdown="# InsightGraph Research Report\n\n## References\n",
        findings=[
            Finding(
                title="Finding",
                summary="Summary",
                evidence_ids=["evidence-1"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Cursor",
                positioning="Editor-first AI coding assistant",
                strengths=["IDE integration"],
                evidence_ids=["evidence-1"],
            )
        ],
        critique=Critique(passed=True, reason="Citations present."),
        tool_call_log=[
            ToolCallRecord(
                subtask_id="collect",
                tool_name="mock_search",
                query=query,
                evidence_count=1,
            )
        ],
        llm_call_log=[
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay-model",
                wire_api="responses",
                success=True,
                duration_ms=8,
            )
        ],
        iterations=1,
    )


def test_main_runs_query_and_writes_markdown():
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_state(query)

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_research_script.main(
        ["Compare AI coding agents"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert observed_queries == ["Compare AI coding agents"]
    assert stderr.getvalue() == ""
    assert stdout.getvalue() == "# InsightGraph Research Report\n\n## References\n"


def test_main_reads_query_from_stdin_dash():
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_state(query)

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_research_script.main(
        ["-"],
        stdin=io.StringIO("  Compare from stdin\n"),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert observed_queries == ["Compare from stdin"]
    assert "# InsightGraph Research Report" in stdout.getvalue()


def test_main_rejects_empty_query_without_running_workflow():
    def fail_run_research(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_research_script.main(
        ["  "],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Research query must not be empty.\n"


def test_main_outputs_cli_aligned_json_payload():
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_research_script.main(
        ["Compare AI coding agents", "--output-json"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=make_state,
    )

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["user_request"] == "Compare AI coding agents"
    assert payload["report_markdown"].startswith("# InsightGraph Research Report")
    assert payload["findings"][0]["title"] == "Finding"
    assert payload["competitive_matrix"][0]["product"] == "Cursor"
    assert payload["critique"]["passed"] is True
    assert payload["tool_call_log"][0]["tool_name"] == "mock_search"
    assert payload["llm_call_log"][0]["wire_api"] == "responses"
    assert payload["iterations"] == 1


def test_main_offline_preset_does_not_apply_live_defaults(monkeypatch):
    clear_live_defaults(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in run_research_script.LIVE_LLM_PRESET_DEFAULTS}
        )
        return make_state(query)

    exit_code = run_research_script.main(
        ["Compare", "--preset", "offline"],
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert observed_env == {
        name: None for name in run_research_script.LIVE_LLM_PRESET_DEFAULTS
    }


def test_main_live_llm_preset_applies_defaults(monkeypatch):
    clear_live_defaults(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in run_research_script.LIVE_LLM_PRESET_DEFAULTS}
        )
        return make_state(query)

    exit_code = run_research_script.main(
        ["Compare", "--preset", "live-llm"],
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert observed_env == run_research_script.LIVE_LLM_PRESET_DEFAULTS


def test_main_returns_one_for_workflow_exception_without_raw_error():
    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret raw provider failure")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_research_script.main(
        ["Compare"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Research workflow failed.\n"
    assert "secret raw provider failure" not in stderr.getvalue()


def test_main_returns_two_for_stdout_write_error_without_traceback():
    stderr = io.StringIO()
    exit_code = run_research_script.main(
        ["Compare"],
        stdin=io.StringIO(),
        stdout=BadStdout(),
        stderr=stderr,
        run_research_func=make_state,
    )

    assert exit_code == 2
    assert stderr.getvalue() == "Failed to write output.\n"
    assert "Traceback" not in stderr.getvalue()


def test_main_returns_two_for_unknown_option_without_traceback():
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_research_script.main(
        ["Compare", "--unknown"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=make_state,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "usage:" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_run_research_script.py -q
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'scripts.run_research'` or `ImportError` because the script does not exist yet.

- [ ] **Step 3: Implement the script wrapper**

Create `scripts/run_research.py` with this content:

```python
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any, TextIO

from insight_graph.cli import (
    LIVE_LLM_PRESET_DEFAULTS,
    ResearchPreset,
    _apply_research_preset,
    _build_research_json_payload,
)
from insight_graph.graph import run_research
from insight_graph.state import GraphState


class ResearchArgumentParser(argparse.ArgumentParser):
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


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    run_research_func: Callable[[str], GraphState] = run_research,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    parser = ResearchArgumentParser(
        description="Run an InsightGraph research workflow.",
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
        "--output-json",
        action="store_true",
        help="Print a safe structured JSON summary instead of Markdown.",
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

    _apply_research_preset(ResearchPreset(args.preset))

    try:
        state = run_research_func(query)
    except Exception:
        stderr.write("Research workflow failed.\n")
        return 1

    try:
        if args.output_json:
            json.dump(
                _build_research_json_payload(state),
                stdout,
                indent=2,
                ensure_ascii=False,
            )
            stdout.write("\n")
        else:
            stdout.write(_format_markdown_output(state.report_markdown or ""))
    except OSError:
        stderr.write("Failed to write output.\n")
        return 2

    return 0


def _read_query(query_arg: str, stdin: TextIO) -> str:
    if query_arg == "-":
        return stdin.read().strip()
    return query_arg.strip()


def _format_markdown_output(report_markdown: str) -> str:
    return report_markdown.rstrip() + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and lint for Task 1**

Run:

```powershell
python -m pytest tests/test_run_research_script.py -q
python -m ruff check scripts/run_research.py tests/test_run_research_script.py
```

Expected: all tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add scripts/run_research.py tests/test_run_research_script.py
git commit -m "feat: add run research script"
```

---

### Task 2: README Documentation

**Files:**
- Modify: `README.md:586-620`

- [ ] **Step 1: Run pre-documentation tests**

Run:

```powershell
python -m pytest tests/test_run_research_script.py tests/test_cli.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Update script status and usage docs**

In `README.md`, replace the `scripts/run_research.py` row in the `## 脚本状态` table with:

```markdown
| `scripts/run_research.py` | 当前可用 | 运行 research workflow，默认输出 Markdown；支持 stdin `-`、`--preset offline\|live-llm` 和 `--output-json` 输出 CLI/API 对齐结构 |
```

After the script table or before the current benchmark usage block, add this section. Use normal fenced `bash` blocks in the README:

~~~markdown
当前 run research 用法：

```bash
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_research.py - < query.txt
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

该脚本复用当前 research workflow。默认 `--preset offline` 保持 deterministic mock evidence；`--preset live-llm` 会使用与 CLI 相同的 live runtime defaults。
~~~

- [ ] **Step 3: Run documentation-adjacent tests**

Run:

```powershell
python -m pytest tests/test_run_research_script.py tests/test_cli.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Commit Task 2**

Run:

```powershell
git add README.md
git commit -m "docs: document run research script"
```

---

### Task 3: Final Verification And Smoke

**Files:**
- Verify only unless a failure requires a targeted fix.

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
python -m pytest tests/test_run_research_script.py tests/test_cli.py -q
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

- [ ] **Step 4: Run Markdown smoke**

Run:

```powershell
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot"
```

Expected stdout contains:

```text
# InsightGraph Research Report
## References
```

- [ ] **Step 5: Run JSON smoke**

Run:

```powershell
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

Expected stdout contains:

```text
"report_markdown"
"competitive_matrix"
"llm_call_log"
```

- [ ] **Step 6: Commit any verification fixes**

If Steps 1-5 required fixes, commit only the targeted fixes:

```powershell
git add scripts/run_research.py tests/test_run_research_script.py README.md
git commit -m "fix: harden run research script"
```

If no files changed, do not create an empty commit.

---

## Self-Review

- Spec coverage: Tasks cover query/stdin input, Markdown output, JSON output, preset behavior, safe exit codes, README docs, focused/full tests, lint, and smoke.
- Placeholder scan: No placeholders remain; every code-changing step includes concrete code or exact README text.
- Type consistency: The plan consistently uses `main(argv, stdin, stdout, stderr, run_research_func) -> int` and imports the existing CLI helpers for preset and JSON payload behavior.
