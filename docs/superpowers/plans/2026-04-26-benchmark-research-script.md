# Benchmark Research Script MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an offline benchmark script that runs fixed research cases and reports deterministic structure/count metrics in JSON or Markdown.

**Architecture:** Keep the benchmark as a standalone script in `scripts/benchmark_research.py` with small pure functions for env isolation, metrics extraction, payload building, and formatting. Tests import the script module directly and monkeypatch `run_research` so benchmark behavior is verified without subprocesses, network, or LLM calls.

**Tech Stack:** Python 3.13 standard library, existing `insight_graph.graph.run_research`, Pydantic `GraphState` models, pytest, ruff.

---

## File Structure

- Create `scripts/benchmark_research.py`: benchmark cases, env cleanup, metrics, JSON/Markdown output, CLI `main(argv)`.
- Create `tests/test_benchmark_research.py`: offline unit tests for payloads, formatting, env cleanup, errors, and reference counting.
- Modify `README.md`: mark benchmark script as current MVP capability and document usage/limits.

---

### Task 1: Add JSON Benchmark Payload

**Files:**
- Create: `scripts/benchmark_research.py`
- Create: `tests/test_benchmark_research.py`

- [ ] **Step 1: Write failing JSON payload tests**

Create `tests/test_benchmark_research.py`:

```python
import os

import scripts.benchmark_research as benchmark_module
from insight_graph.state import CompetitiveMatrixRow, Critique, Evidence, Finding, GraphState, ToolCallRecord


def make_benchmark_state(query: str) -> GraphState:
    return GraphState(
        user_request=query,
        evidence_pool=[
            Evidence(
                id="cursor-pricing",
                subtask_id="collect",
                title="Cursor Pricing",
                source_url="https://cursor.com/pricing",
                snippet="Cursor pricing evidence.",
                source_type="official_site",
                verified=True,
            ),
            Evidence(
                id="copilot-docs",
                subtask_id="collect",
                title="GitHub Copilot Documentation",
                source_url="https://docs.github.com/en/copilot",
                snippet="Copilot documentation evidence.",
                source_type="docs",
                verified=True,
            ),
        ],
        findings=[
            Finding(
                title="Packaging differs",
                summary="Cursor and Copilot use different packaging signals.",
                evidence_ids=["cursor-pricing"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Cursor",
                positioning="Official product positioning signal",
                strengths=["Official/documented source coverage"],
                evidence_ids=["cursor-pricing"],
            )
        ],
        critique=Critique(passed=True, reason="Findings cite verified evidence."),
        tool_call_log=[
            ToolCallRecord(
                subtask_id="collect",
                tool_name="mock_search",
                query=query,
                evidence_count=2,
            )
        ],
        report_markdown=(
            "# InsightGraph Research Report\n\n"
            "## Key Findings\n\n"
            "Packaging differs. [1]\n\n"
            "## Competitive Matrix\n\n"
            "| Product | Positioning | Strengths | Evidence |\n"
            "| --- | --- | --- | --- |\n"
            "| Cursor | Official product positioning signal | Official/documented source coverage | [1] |\n\n"
            "## References\n\n"
            "[1] Cursor Pricing. https://cursor.com/pricing\n"
            "[2] GitHub Copilot Documentation. https://docs.github.com/en/copilot\n"
        ),
    )


def test_build_benchmark_payload_contains_case_metrics(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return make_benchmark_state(query)

    monkeypatch.setattr(benchmark_module.time, "perf_counter", iter([1.0, 1.025]).__next__)

    payload = benchmark_module.build_benchmark_payload(
        ["Compare Cursor and GitHub Copilot"],
        run_research_func=fake_run_research,
    )

    assert payload["cases"] == [
        {
            "query": "Compare Cursor and GitHub Copilot",
            "duration_ms": 25,
            "finding_count": 1,
            "competitive_matrix_row_count": 1,
            "reference_count": 2,
            "tool_call_count": 1,
            "llm_call_count": 0,
            "critique_passed": True,
            "report_has_competitive_matrix": True,
        }
    ]
    assert payload["summary"] == {
        "case_count": 1,
        "total_duration_ms": 25,
        "all_critique_passed": True,
        "total_findings": 1,
        "total_competitive_matrix_rows": 1,
        "total_references": 2,
        "total_tool_calls": 1,
        "total_llm_calls": 0,
    }


def test_benchmark_clears_runtime_opt_in_env_for_case(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env["INSIGHT_GRAPH_USE_WEB_SEARCH"] = os.getenv("INSIGHT_GRAPH_USE_WEB_SEARCH")
        observed_env["INSIGHT_GRAPH_ANALYST_PROVIDER"] = os.getenv("INSIGHT_GRAPH_ANALYST_PROVIDER")
        return make_benchmark_state(query)

    benchmark_module.build_benchmark_payload(
        ["Compare Cursor and GitHub Copilot"],
        run_research_func=fake_run_research,
    )

    assert observed_env == {
        "INSIGHT_GRAPH_USE_WEB_SEARCH": None,
        "INSIGHT_GRAPH_ANALYST_PROVIDER": None,
    }
    assert os.getenv("INSIGHT_GRAPH_USE_WEB_SEARCH") == "1"
    assert os.getenv("INSIGHT_GRAPH_ANALYST_PROVIDER") == "llm"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_benchmark_research.py::test_build_benchmark_payload_contains_case_metrics tests/test_benchmark_research.py::test_benchmark_clears_runtime_opt_in_env_for_case -q
```

Expected: FAIL because `scripts.benchmark_research` does not exist.

- [ ] **Step 3: Implement benchmark script JSON payload**

Create `scripts/benchmark_research.py`:

```python
import os
import re
import time
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from typing import Any

from insight_graph.graph import run_research
from insight_graph.state import GraphState

BENCHMARK_CASES = [
    "Compare Cursor, OpenCode, and GitHub Copilot",
    "Analyze AI coding agents market positioning",
    "Compare Claude Code, Codeium, and Windsurf",
]

OFFLINE_ENV_VARS = [
    "INSIGHT_GRAPH_ANALYST_PROVIDER",
    "INSIGHT_GRAPH_REPORTER_PROVIDER",
    "INSIGHT_GRAPH_LLM_API_KEY",
    "INSIGHT_GRAPH_LLM_BASE_URL",
    "INSIGHT_GRAPH_LLM_MODEL",
    "INSIGHT_GRAPH_USE_WEB_SEARCH",
    "INSIGHT_GRAPH_USE_GITHUB_SEARCH",
    "INSIGHT_GRAPH_USE_NEWS_SEARCH",
    "INSIGHT_GRAPH_USE_DOCUMENT_READER",
    "INSIGHT_GRAPH_USE_READ_FILE",
    "INSIGHT_GRAPH_USE_LIST_DIRECTORY",
    "INSIGHT_GRAPH_USE_WRITE_FILE",
    "INSIGHT_GRAPH_SEARCH_PROVIDER",
    "INSIGHT_GRAPH_RELEVANCE_FILTER",
    "INSIGHT_GRAPH_RELEVANCE_JUDGE",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
]

REFERENCE_LINE_PATTERN = re.compile(r"(?m)^\[\d+]\s+")
SAFE_WORKFLOW_ERROR = "Research workflow failed."


@contextmanager
def offline_environment() -> Iterable[None]:
    previous_values = {name: os.environ.get(name) for name in OFFLINE_ENV_VARS}
    try:
        for name in OFFLINE_ENV_VARS:
            os.environ.pop(name, None)
        yield
    finally:
        for name, value in previous_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def build_benchmark_payload(
    cases: list[str] | None = None,
    run_research_func: Callable[[str], GraphState] = run_research,
) -> dict[str, Any]:
    case_queries = cases if cases is not None else BENCHMARK_CASES
    case_results = [_run_case(query, run_research_func) for query in case_queries]
    return {"cases": case_results, "summary": _build_summary(case_results)}


def _run_case(
    query: str,
    run_research_func: Callable[[str], GraphState],
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with offline_environment():
            state = run_research_func(query)
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return _error_case_result(query, duration_ms)

    duration_ms = int((time.perf_counter() - started) * 1000)
    return _case_result_from_state(query, duration_ms, state)


def _case_result_from_state(query: str, duration_ms: int, state: GraphState) -> dict[str, Any]:
    report_markdown = state.report_markdown or ""
    return {
        "query": query,
        "duration_ms": duration_ms,
        "finding_count": len(state.findings),
        "competitive_matrix_row_count": len(state.competitive_matrix),
        "reference_count": count_references(report_markdown),
        "tool_call_count": len(state.tool_call_log),
        "llm_call_count": len(state.llm_call_log),
        "critique_passed": bool(state.critique and state.critique.passed),
        "report_has_competitive_matrix": "## Competitive Matrix" in report_markdown,
    }


def _error_case_result(query: str, duration_ms: int) -> dict[str, Any]:
    return {
        "query": query,
        "duration_ms": duration_ms,
        "finding_count": 0,
        "competitive_matrix_row_count": 0,
        "reference_count": 0,
        "tool_call_count": 0,
        "llm_call_count": 0,
        "critique_passed": False,
        "report_has_competitive_matrix": False,
        "error": SAFE_WORKFLOW_ERROR,
    }


def count_references(report_markdown: str) -> int:
    references_start = report_markdown.find("## References")
    if references_start == -1:
        return 0
    references_section = report_markdown[references_start:]
    return len(REFERENCE_LINE_PATTERN.findall(references_section))


def _build_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_count": len(case_results),
        "total_duration_ms": sum(int(item["duration_ms"]) for item in case_results),
        "all_critique_passed": all(bool(item["critique_passed"]) for item in case_results),
        "total_findings": sum(int(item["finding_count"]) for item in case_results),
        "total_competitive_matrix_rows": sum(
            int(item["competitive_matrix_row_count"]) for item in case_results
        ),
        "total_references": sum(int(item["reference_count"]) for item in case_results),
        "total_tool_calls": sum(int(item["tool_call_count"]) for item in case_results),
        "total_llm_calls": sum(int(item["llm_call_count"]) for item in case_results),
    }


```

- [ ] **Step 4: Run JSON tests and lint**

Run:

```powershell
python -m pytest tests/test_benchmark_research.py::test_build_benchmark_payload_contains_case_metrics tests/test_benchmark_research.py::test_benchmark_clears_runtime_opt_in_env_for_case -q
python -m ruff check scripts/benchmark_research.py tests/test_benchmark_research.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add scripts/benchmark_research.py tests/test_benchmark_research.py
git commit -m "feat: add research benchmark payload"
```

---

### Task 2: Add Markdown Output And Error Rows

**Files:**
- Modify: `scripts/benchmark_research.py`
- Modify: `tests/test_benchmark_research.py`

- [ ] **Step 1: Add failing Markdown and error tests**

Append to `tests/test_benchmark_research.py`:

```python
def test_format_markdown_outputs_case_and_summary_tables() -> None:
    payload = {
        "cases": [
            {
                "query": "Compare Cursor | Copilot\nNow",
                "duration_ms": 25,
                "finding_count": 1,
                "competitive_matrix_row_count": 1,
                "reference_count": 2,
                "tool_call_count": 1,
                "llm_call_count": 0,
                "critique_passed": True,
                "report_has_competitive_matrix": True,
            }
        ],
        "summary": {
            "case_count": 1,
            "total_duration_ms": 25,
            "all_critique_passed": True,
            "total_findings": 1,
            "total_competitive_matrix_rows": 1,
            "total_references": 2,
            "total_tool_calls": 1,
            "total_llm_calls": 0,
        },
    }

    markdown = benchmark_module.format_markdown(payload)

    assert markdown.startswith("# InsightGraph Benchmark\n")
    assert "| Query | Duration ms | Findings | Matrix rows | References | Tool calls | LLM calls | Critique passed | Matrix section |" in markdown
    assert "Compare Cursor \\| Copilot Now" in markdown
    assert "## Summary" in markdown
    assert "| 1 | 25 | true | 1 | 1 | 2 | 1 | 0 |" in markdown


def test_build_benchmark_payload_records_safe_error() -> None:
    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider payload and local path")

    payload = benchmark_module.build_benchmark_payload(
        ["Compare Cursor and GitHub Copilot"],
        run_research_func=fail_run_research,
    )

    case = payload["cases"][0]
    assert case["error"] == "Research workflow failed."
    assert case["finding_count"] == 0
    assert case["critique_passed"] is False
    assert "secret provider payload" not in str(payload)
    assert payload["summary"]["all_critique_passed"] is False


def test_format_markdown_includes_safe_errors_section() -> None:
    payload = {
        "cases": [
            {
                "query": "Compare Cursor",
                "duration_ms": 2,
                "finding_count": 0,
                "competitive_matrix_row_count": 0,
                "reference_count": 0,
                "tool_call_count": 0,
                "llm_call_count": 0,
                "critique_passed": False,
                "report_has_competitive_matrix": False,
                "error": "Research workflow failed.",
            }
        ],
        "summary": {
            "case_count": 1,
            "total_duration_ms": 2,
            "all_critique_passed": False,
            "total_findings": 0,
            "total_competitive_matrix_rows": 0,
            "total_references": 0,
            "total_tool_calls": 0,
            "total_llm_calls": 0,
        },
    }

    markdown = benchmark_module.format_markdown(payload)

    assert "## Errors" in markdown
    assert "| Compare Cursor | Research workflow failed. |" in markdown
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_benchmark_research.py::test_format_markdown_outputs_case_and_summary_tables tests/test_benchmark_research.py::test_build_benchmark_payload_records_safe_error tests/test_benchmark_research.py::test_format_markdown_includes_safe_errors_section -q
```

Expected: Markdown tests fail because `format_markdown()` is not implemented.

- [ ] **Step 3: Implement Markdown formatter**

Add CLI imports near the top of `scripts/benchmark_research.py`:

```python
import argparse
import json
import sys
```

Add `main()`, `format_markdown()`, and helpers near the end of the file:

```python
def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# InsightGraph Benchmark",
        "",
        "| Query | Duration ms | Findings | Matrix rows | References | Tool calls | LLM calls | Critique passed | Matrix section |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for item in payload["cases"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(str(item["query"])),
                    str(item["duration_ms"]),
                    str(item["finding_count"]),
                    str(item["competitive_matrix_row_count"]),
                    str(item["reference_count"]),
                    str(item["tool_call_count"]),
                    str(item["llm_call_count"]),
                    _format_bool(bool(item["critique_passed"])),
                    _format_bool(bool(item["report_has_competitive_matrix"])),
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
            "| Cases | Total duration ms | All critique passed | Total findings | Total matrix rows | Total references | Total tool calls | Total LLM calls |",
            "| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
            "| "
            + " | ".join(
                [
                    str(summary["case_count"]),
                    str(summary["total_duration_ms"]),
                    _format_bool(bool(summary["all_critique_passed"])),
                    str(summary["total_findings"]),
                    str(summary["total_competitive_matrix_rows"]),
                    str(summary["total_references"]),
                    str(summary["total_tool_calls"]),
                    str(summary["total_llm_calls"]),
                ]
            )
            + " |",
        ]
    )
    error_lines = _format_error_lines(payload["cases"])
    if error_lines:
        lines.extend(error_lines)
    return "\n".join(lines) + "\n"


def _format_error_lines(case_results: list[dict[str, Any]]) -> list[str]:
    errors = [item for item in case_results if "error" in item]
    if not errors:
        return []
    lines = ["", "## Errors", "", "| Query | Error |", "| --- | --- |"]
    for item in errors:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(str(item["query"])),
                    _markdown_table_cell(str(item["error"])),
                ]
            )
            + " |"
        )
    return lines


def _markdown_table_cell(value: str) -> str:
    return " ".join(value.replace("|", r"\|").splitlines())


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run offline InsightGraph research benchmarks.")
    parser.add_argument("--markdown", action="store_true", help="Print Markdown instead of JSON.")
    args = parser.parse_args(argv)
    payload = build_benchmark_payload()
    if args.markdown:
        print(format_markdown(payload), end="")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run benchmark tests and lint**

Run:

```powershell
python -m pytest tests/test_benchmark_research.py -q
python -m ruff check scripts/benchmark_research.py tests/test_benchmark_research.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add scripts/benchmark_research.py tests/test_benchmark_research.py
git commit -m "feat: format research benchmark output"
```

---

### Task 3: Document Benchmark Script

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README script section**

In `README.md`, change the heading:

```markdown
## 计划脚本（后续路线图）
```

to:

```markdown
## 脚本
```

Update the `scripts/benchmark_research.py` row to:

```markdown
| `scripts/benchmark_research.py` | 当前可用：离线运行固定 benchmark cases，输出 JSON 或 `--markdown` 表格；不访问公网、不调用 LLM、不做阈值 gate |
```

Keep the other script rows as future/planned descriptions.

Add a short subsection after the script table:

```markdown
当前 benchmark 用法：

```bash
python scripts/benchmark_research.py
python scripts/benchmark_research.py --markdown
```

该脚本会在进程内清理会改变默认工具/LLM 行为的 opt-in 环境变量，确保 benchmark 使用 offline deterministic workflow。
```

- [ ] **Step 2: Run docs-related verification**

Run:

```powershell
python -m pytest tests/test_benchmark_research.py -q
python -m ruff check .
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 3: Commit Task 3**

Run:

```powershell
git add README.md
git commit -m "docs: document research benchmark script"
```

---

### Task 4: Final Verification And Smoke

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_benchmark_research.py tests/test_graph.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full tests and lint**

Run:

```powershell
python -m pytest -q
python -m ruff check .
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 3: Reinstall editable checkout**

Run:

```powershell
python -m pip install -e .
```

Expected: command succeeds and installs current checkout.

- [ ] **Step 4: Run JSON smoke**

Run:

```powershell
python scripts/benchmark_research.py
```

Expected: output contains these strings:

```text
"cases"
"summary"
"total_llm_calls": 0
```

- [ ] **Step 5: Run Markdown smoke**

Run:

```powershell
python scripts/benchmark_research.py --markdown
```

Expected: output contains these strings:

```text
# InsightGraph Benchmark
## Summary
```

- [ ] **Step 6: Inspect git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree on the implementation branch.
