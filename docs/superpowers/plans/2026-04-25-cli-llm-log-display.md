# CLI LLM Log Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `--show-llm-log` CLI flag that appends safe LLM call metadata after the Markdown report.

**Architecture:** Keep the feature local to `src/insight_graph/cli.py` because this is presentation-only behavior. Add small Markdown formatting helpers that read only existing `LLMCallRecord` fields and append the section only when the flag is set.

**Tech Stack:** Python 3.13, Typer, Pydantic models, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/cli.py`: add `--show-llm-log`, safe Markdown table formatting helpers, and opt-in section appending.
- Modify `tests/test_cli.py`: add fake-state CLI tests for default output, populated log output, empty log output, and Markdown escaping/privacy.
- Modify `README.md`: document `--show-llm-log` under LLM Observability.

---

### Task 1: Add CLI LLM Log Display

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/insight_graph/cli.py`

- [ ] **Step 1: Write failing CLI tests**

Update the import in `tests/test_cli.py`:

```python
from insight_graph.state import GraphState, LLMCallRecord
```

Add these tests at the end of `tests/test_cli.py`:

```python
def test_cli_research_does_not_show_llm_log_by_default(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
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

    result = runner.invoke(app, ["research", "Compare AI coding agents"])

    assert result.exit_code == 0
    assert "# Report" in result.output
    assert "## LLM Call Log" not in result.output
    assert "relay-model" not in result.output


def test_cli_research_show_llm_log_appends_metadata_table(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.extend(
            [
                LLMCallRecord(
                    stage="relevance",
                    provider="openai_compatible",
                    model="relay-model",
                    success=True,
                    duration_ms=7,
                ),
                LLMCallRecord(
                    stage="reporter",
                    provider="llm",
                    model="relay-model",
                    success=False,
                    duration_ms=9,
                    error="ReporterFallbackError: LLM call failed.",
                ),
            ]
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "# Report" in result.output
    assert "## LLM Call Log" in result.output
    assert "| Stage | Provider | Model | Success | Duration ms | Error |" in result.output
    assert "| relevance | openai_compatible | relay-model | true | 7 |  |" in result.output
    assert (
        "| reporter | llm | relay-model | false | 9 | "
        "ReporterFallbackError: LLM call failed. |"
    ) in result.output


def test_cli_research_show_llm_log_reports_empty_log(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "# Report" in result.output
    assert "## LLM Call Log" in result.output
    assert "No LLM calls were recorded." in result.output


def test_cli_research_show_llm_log_escapes_cells_and_omits_raw_payloads(
    monkeypatch,
) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay|model\nsecond-line",
                success=False,
                duration_ms=3,
                error="RuntimeError: LLM call failed.",
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "relay\\|model second-line" in result.output
    assert "RuntimeError: LLM call failed." in result.output
    assert "Sensitive prompt" not in result.output
    assert "Raw response" not in result.output
    assert "sk-secret" not in result.output
    assert "Authorization" not in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_research_does_not_show_llm_log_by_default tests/test_cli.py::test_cli_research_show_llm_log_appends_metadata_table tests/test_cli.py::test_cli_research_show_llm_log_reports_empty_log tests/test_cli.py::test_cli_research_show_llm_log_escapes_cells_and_omits_raw_payloads -q
```

Expected: FAIL because `--show-llm-log` does not exist and the CLI has no LLM log formatting helper yet.

- [ ] **Step 3: Add CLI formatting helpers and option**

In `src/insight_graph/cli.py`, update imports:

```python
from insight_graph.state import LLMCallRecord
```

Add these helpers after `_configure_output_encoding`:

```python
def _format_llm_call_log(records: list[LLMCallRecord]) -> str:
    lines = ["## LLM Call Log", ""]
    if not records:
        lines.append("No LLM calls were recorded.")
        return "\n".join(lines)

    lines.extend(
        [
            "| Stage | Provider | Model | Success | Duration ms | Error |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for record in records:
        lines.append(
            "| "
            f"{_markdown_table_cell(record.stage)} | "
            f"{_markdown_table_cell(record.provider)} | "
            f"{_markdown_table_cell(record.model)} | "
            f"{str(record.success).lower()} | "
            f"{record.duration_ms} | "
            f"{_markdown_table_cell(record.error or '')} |"
        )
    return "\n".join(lines)


def _markdown_table_cell(value: str) -> str:
    return " ".join(value.replace("|", r"\|").splitlines())
```

Update the `research` command signature and output logic:

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
) -> None:
    """Run a research workflow and print a Markdown report."""
    _apply_research_preset(preset)
    state = run_research(query)
    output = state.report_markdown or ""
    if show_llm_log:
        output = f"{output.rstrip()}\n\n{_format_llm_call_log(state.llm_call_log)}\n"
    typer.echo(output)
```

- [ ] **Step 4: Run focused CLI tests to verify they pass**

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_research_does_not_show_llm_log_by_default tests/test_cli.py::test_cli_research_show_llm_log_appends_metadata_table tests/test_cli.py::test_cli_research_show_llm_log_reports_empty_log tests/test_cli.py::test_cli_research_show_llm_log_escapes_cells_and_omits_raw_payloads -q
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
git commit -m "feat: show llm call log in cli"
```

---

### Task 2: Document CLI LLM Log Display

**Files:**
- Modify: `README.md`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Update README**

In `README.md`, find the `### LLM Observability` section and add this paragraph after the metadata/privacy explanation:

````markdown
Use `--show-llm-log` to append the in-memory LLM call metadata after the Markdown report:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --show-llm-log
```

The appended table is opt-in and contains only stage, provider, model, success, duration, and sanitized error metadata.
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
git commit -m "docs: document cli llm log display"
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

- [ ] **Step 2: Run offline CLI smoke without log flag**

Run:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

Expected: Markdown report is printed and does not include `## LLM Call Log`.

- [ ] **Step 3: Run offline CLI smoke with log flag**

Run:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --show-llm-log
```

Expected: Markdown report is printed and includes:

```markdown
## LLM Call Log

No LLM calls were recorded.
```

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected: clean working tree on the implementation branch.
