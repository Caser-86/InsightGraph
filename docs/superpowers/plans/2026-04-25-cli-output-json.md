# CLI Output JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `--output-json` CLI mode that emits a safe structured summary of a research run.

**Architecture:** Keep JSON output local to `src/insight_graph/cli.py` as presentation behavior. Add a helper that explicitly selects safe summary fields from `GraphState`, and make JSON mode take precedence over Markdown `--show-llm-log` output.

**Tech Stack:** Python 3.13, Typer, Pydantic, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/cli.py`: add `--output-json`, JSON payload helper, and JSON-first output branch.
- Modify `tests/test_cli.py`: add fake-state tests for parseable JSON, included/omitted fields, privacy, and `--show-llm-log` precedence.
- Modify `README.md`: document `--output-json` near CLI/live/observability usage.

---

### Task 1: Add CLI JSON Output Mode

**Files:**
- Modify: `src/insight_graph/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI JSON tests**

Add `json` to the imports at the top of `tests/test_cli.py`:

```python
import json
import os
```

Update the state imports in `tests/test_cli.py`:

```python
from insight_graph.state import (
    Critique,
    Evidence,
    Finding,
    GraphState,
    LLMCallRecord,
    Subtask,
    ToolCallRecord,
)
```

Add these tests at the end of `tests/test_cli.py`:

```python
def test_cli_research_output_json_emits_parseable_summary(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(
            user_request=query,
            report_markdown="# Report\n",
            findings=[
                Finding(
                    title="Pricing differs",
                    summary="Pricing and packaging differ.",
                    evidence_ids=["cursor-pricing"],
                )
            ],
            critique=Critique(passed=True, reason="Enough evidence."),
            iterations=1,
        )
        state.tool_call_log.append(
            ToolCallRecord(
                subtask_id="collect",
                tool_name="mock_search",
                query=query,
                evidence_count=2,
            )
        )
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay-model",
                success=True,
                duration_ms=12,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--output-json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "user_request": "Compare AI coding agents",
        "report_markdown": "# Report\n",
        "findings": [
            {
                "title": "Pricing differs",
                "summary": "Pricing and packaging differ.",
                "evidence_ids": ["cursor-pricing"],
            }
        ],
        "critique": {
            "passed": True,
            "reason": "Enough evidence.",
            "missing_topics": [],
        },
        "tool_call_log": [
            {
                "subtask_id": "collect",
                "tool_name": "mock_search",
                "query": "Compare AI coding agents",
                "evidence_count": 2,
                "filtered_count": 0,
                "success": True,
                "error": None,
            }
        ],
        "llm_call_log": [
            {
                "stage": "analyst",
                "provider": "llm",
                "model": "relay-model",
                "success": True,
                "duration_ms": 12,
                "error": None,
            }
        ],
        "iterations": 1,
    }


def test_cli_research_default_output_is_not_json(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents"])

    assert result.exit_code == 0
    assert result.output.startswith("# Report")
    try:
        json.loads(result.output)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("Default research output should remain Markdown")


def test_cli_research_output_json_omits_evidence_and_private_strings(
    monkeypatch,
) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(
            user_request=query,
            report_markdown="# Report\n",
            subtasks=[Subtask(id="secret-subtask", description="Sensitive prompt")],
            evidence_pool=[
                Evidence(
                    id="secret-evidence",
                    subtask_id="collect",
                    title="Raw response",
                    source_url="https://example.com/private",
                    snippet="sk-secret Authorization request-body Sensitive prompt",
                    verified=True,
                )
            ],
            global_evidence_pool=[
                Evidence(
                    id="global-secret-evidence",
                    subtask_id="collect",
                    title="Header",
                    source_url="https://example.com/global-private",
                    snippet="Raw response should not be exported",
                    verified=True,
                )
            ],
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--output-json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "subtasks" not in payload
    assert "evidence_pool" not in payload
    assert "global_evidence_pool" not in payload
    serialized = json.dumps(payload)
    assert "secret-subtask" not in serialized
    assert "secret-evidence" not in serialized
    assert "global-secret-evidence" not in serialized
    assert "Sensitive prompt" not in serialized
    assert "Raw response" not in serialized
    assert "sk-secret" not in serialized
    assert "Authorization" not in serialized
    assert "request-body" not in serialized


def test_cli_research_output_json_takes_precedence_over_show_llm_log(
    monkeypatch,
) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="reporter",
                provider="llm",
                model="relay-model",
                success=True,
                duration_ms=4,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "research",
            "Compare AI coding agents",
            "--output-json",
            "--show-llm-log",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["llm_call_log"][0]["stage"] == "reporter"
    assert "## LLM Call Log" not in result.output
    assert "| Stage | Provider | Model |" not in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_research_output_json_emits_parseable_summary tests/test_cli.py::test_cli_research_default_output_is_not_json tests/test_cli.py::test_cli_research_output_json_omits_evidence_and_private_strings tests/test_cli.py::test_cli_research_output_json_takes_precedence_over_show_llm_log -q
```

Expected: FAIL because `--output-json` does not exist. The default-output test may pass because it describes existing Markdown behavior.

- [ ] **Step 3: Add JSON serializer helper and CLI option**

In `src/insight_graph/cli.py`, add `json` to the imports:

```python
import json
import os
import sys
```

Update the state import:

```python
from insight_graph.state import GraphState, LLMCallRecord
```

Add this helper after `_markdown_table_cell`:

```python
def _build_research_json_payload(state: GraphState) -> dict[str, object]:
    return {
        "user_request": state.user_request,
        "report_markdown": state.report_markdown or "",
        "findings": [finding.model_dump(mode="json") for finding in state.findings],
        "critique": state.critique.model_dump(mode="json")
        if state.critique is not None
        else None,
        "tool_call_log": [
            record.model_dump(mode="json") for record in state.tool_call_log
        ],
        "llm_call_log": [record.model_dump(mode="json") for record in state.llm_call_log],
        "iterations": state.iterations,
    }
```

Update the `research` command signature and output branch:

```python
@app.command()
def research(
    query: str,
    preset: Annotated[
        ResearchPreset,
        typer.Option("--preset", help="Runtime preset: offline or live-llm."),
    ] = ResearchPreset.offline,
    show_llm_log: Annotated[
        bool,
        typer.Option(
            "--show-llm-log",
            help="Append safe LLM call metadata after the Markdown report.",
        ),
    ] = False,
    output_json: Annotated[
        bool,
        typer.Option(
            "--output-json",
            help="Print a safe structured JSON summary instead of Markdown.",
        ),
    ] = False,
) -> None:
    """Run a research workflow and print a Markdown report."""
    _apply_research_preset(preset)
    state = run_research(query)
    if output_json:
        typer.echo(
            json.dumps(
                _build_research_json_payload(state),
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    output = state.report_markdown or ""
    if show_llm_log:
        output = f"{output.rstrip()}\n\n{_format_llm_call_log(state.llm_call_log)}\n"
    typer.echo(output)
```

- [ ] **Step 4: Run focused tests to verify they pass**

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_research_output_json_emits_parseable_summary tests/test_cli.py::test_cli_research_default_output_is_not_json tests/test_cli.py::test_cli_research_output_json_omits_evidence_and_private_strings tests/test_cli.py::test_cli_research_output_json_takes_precedence_over_show_llm_log -q
```

Expected: PASS.

- [ ] **Step 5: Run all CLI tests and lint**

Run:

```bash
python -m pytest tests/test_cli.py -q
python -m ruff check src/insight_graph/cli.py tests/test_cli.py
```

Expected: all CLI tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add src/insight_graph/cli.py tests/test_cli.py
git commit -m "feat: add cli json output"
```

---

### Task 2: Document CLI JSON Output

**Files:**
- Modify: `README.md`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Update README**

In `README.md`, near the CLI usage or observability section, add this paragraph:

````markdown
Use `--output-json` when scripts need a structured summary instead of Markdown:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

JSON output includes `user_request`, `report_markdown`, `findings`, `critique`, `tool_call_log`, `llm_call_log`, and `iterations`. It intentionally omits `evidence_pool` and `global_evidence_pool` to avoid dumping fetched snippets. If `--output-json` and `--show-llm-log` are both provided, JSON output takes precedence.
````

- [ ] **Step 2: Run documentation-adjacent verification**

Run:

```bash
python -m pytest tests/test_cli.py -q
python -m ruff check tests/test_cli.py src/insight_graph/cli.py
```

Expected: CLI tests pass and ruff reports `All checks passed!`.

- [ ] **Step 3: Commit Task 2**

Run:

```bash
git add README.md
git commit -m "docs: document cli json output"
```

---

### Task 3: Final Verification

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run full tests and lint**

Run:

```bash
python -m pytest -v
python -m ruff check .
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 2: Run offline CLI smoke with default Markdown**

Run:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

Expected: Markdown report is printed and the output does not start with `{`.

- [ ] **Step 3: Run offline CLI smoke with JSON output**

Run:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

Expected: parseable pretty JSON is printed with top-level `user_request`, `report_markdown`, `findings`, `critique`, `tool_call_log`, `llm_call_log`, and `iterations` fields.

- [ ] **Step 4: Run offline CLI smoke with JSON and LLM log flags together**

Run:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json --show-llm-log
```

Expected: parseable JSON is printed and no Markdown `## LLM Call Log` heading appears outside the JSON string values.

- [ ] **Step 5: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected: clean working tree on the implementation branch.
