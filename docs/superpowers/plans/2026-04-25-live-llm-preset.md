# Live LLM Preset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--preset live-llm` to the research CLI so users can enable live web search, LLM relevance, LLM Analyst, and LLM Reporter with one explicit switch while preserving default offline behavior.

**Architecture:** Keep preset behavior in `src/insight_graph/cli.py` as a small runtime environment helper. The helper only fills missing environment variables for the current process and does not mutate user-level or system-level environment configuration. Tests monkeypatch `run_research` where needed so they never call DuckDuckGo or external LLM APIs.

**Tech Stack:** Python 3.13, Typer, pytest, ruff, existing InsightGraph `GraphState` model.

---

## File Structure

- Modify `src/insight_graph/cli.py`: add `ResearchPreset`, live preset default mapping, `_apply_research_preset()`, and a `--preset` option on `research()`.
- Modify `tests/test_cli.py`: extend env cleanup, add fake workflow tests for live preset behavior, env precedence, and invalid preset rejection.
- Modify `README.md`: document default offline CLI and `--preset live-llm` usage.

---

### Task 1: Add Preset Helper

**Files:**
- Modify: `src/insight_graph/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing helper tests**

Add these imports near the top of `tests/test_cli.py`:

```python
import os
```

Extend `clear_llm_env()` so preset env values are also cleared:

```python
def clear_llm_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_PROVIDER",
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_LLM_BASE_URL",
        "INSIGHT_GRAPH_LLM_MODEL",
        "INSIGHT_GRAPH_USE_WEB_SEARCH",
        "INSIGHT_GRAPH_SEARCH_PROVIDER",
        "INSIGHT_GRAPH_RELEVANCE_FILTER",
        "INSIGHT_GRAPH_RELEVANCE_JUDGE",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.delenv(name, raising=False)
```

Add these tests below the existing CLI output encoding tests:

```python
def test_apply_live_llm_preset_sets_missing_runtime_defaults(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    cli_module._apply_research_preset(cli_module.ResearchPreset.live_llm)

    assert os.environ["INSIGHT_GRAPH_USE_WEB_SEARCH"] == "1"
    assert os.environ["INSIGHT_GRAPH_SEARCH_PROVIDER"] == "duckduckgo"
    assert os.environ["INSIGHT_GRAPH_RELEVANCE_FILTER"] == "1"
    assert os.environ["INSIGHT_GRAPH_RELEVANCE_JUDGE"] == "openai_compatible"
    assert os.environ["INSIGHT_GRAPH_ANALYST_PROVIDER"] == "llm"
    assert os.environ["INSIGHT_GRAPH_REPORTER_PROVIDER"] == "llm"


def test_apply_live_llm_preset_preserves_explicit_env_values(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "deterministic")

    cli_module._apply_research_preset(cli_module.ResearchPreset.live_llm)

    assert os.environ["INSIGHT_GRAPH_SEARCH_PROVIDER"] == "mock"
    assert os.environ["INSIGHT_GRAPH_REPORTER_PROVIDER"] == "deterministic"
    assert os.environ["INSIGHT_GRAPH_USE_WEB_SEARCH"] == "1"
    assert os.environ["INSIGHT_GRAPH_ANALYST_PROVIDER"] == "llm"


def test_apply_offline_preset_does_not_set_live_defaults(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    cli_module._apply_research_preset(cli_module.ResearchPreset.offline)

    assert "INSIGHT_GRAPH_USE_WEB_SEARCH" not in os.environ
    assert "INSIGHT_GRAPH_SEARCH_PROVIDER" not in os.environ
    assert "INSIGHT_GRAPH_RELEVANCE_FILTER" not in os.environ
    assert "INSIGHT_GRAPH_RELEVANCE_JUDGE" not in os.environ
    assert "INSIGHT_GRAPH_ANALYST_PROVIDER" not in os.environ
    assert "INSIGHT_GRAPH_REPORTER_PROVIDER" not in os.environ
```

- [ ] **Step 2: Run helper tests to verify they fail**

Run:

```bash
python -m pytest tests/test_cli.py::test_apply_live_llm_preset_sets_missing_runtime_defaults tests/test_cli.py::test_apply_live_llm_preset_preserves_explicit_env_values tests/test_cli.py::test_apply_offline_preset_does_not_set_live_defaults -q
```

Expected: FAIL with `AttributeError` because `ResearchPreset` and `_apply_research_preset` do not exist yet.

- [ ] **Step 3: Implement the minimal helper**

Update `src/insight_graph/cli.py` imports and add the preset definitions above `_configure_output_encoding()`:

```python
import os
import sys
from enum import Enum

import typer

from insight_graph.graph import run_research

app = typer.Typer(help="InsightGraph research workflow CLI")


class ResearchPreset(str, Enum):
    offline = "offline"
    live_llm = "live-llm"


LIVE_LLM_PRESET_DEFAULTS = {
    "INSIGHT_GRAPH_USE_WEB_SEARCH": "1",
    "INSIGHT_GRAPH_SEARCH_PROVIDER": "duckduckgo",
    "INSIGHT_GRAPH_RELEVANCE_FILTER": "1",
    "INSIGHT_GRAPH_RELEVANCE_JUDGE": "openai_compatible",
    "INSIGHT_GRAPH_ANALYST_PROVIDER": "llm",
    "INSIGHT_GRAPH_REPORTER_PROVIDER": "llm",
}


def _apply_research_preset(preset: ResearchPreset) -> None:
    if preset == ResearchPreset.offline:
        return

    for name, value in LIVE_LLM_PRESET_DEFAULTS.items():
        os.environ.setdefault(name, value)
```

Keep the existing `_configure_output_encoding()`, `main()`, and `research()` behavior unchanged in this task.

- [ ] **Step 4: Run helper tests to verify they pass**

Run:

```bash
python -m pytest tests/test_cli.py::test_apply_live_llm_preset_sets_missing_runtime_defaults tests/test_cli.py::test_apply_live_llm_preset_preserves_explicit_env_values tests/test_cli.py::test_apply_offline_preset_does_not_set_live_defaults -q
```

Expected: PASS.

- [ ] **Step 5: Run CLI test file**

Run:

```bash
python -m pytest tests/test_cli.py -q
```

Expected: all CLI tests pass.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add src/insight_graph/cli.py tests/test_cli.py
git commit -m "feat: add live llm preset helper"
```

---

### Task 2: Wire Preset Into CLI Command

**Files:**
- Modify: `src/insight_graph/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI integration tests**

Add this import to `tests/test_cli.py`:

```python
from insight_graph.state import GraphState
```

Add these tests below the helper tests:

```python
def test_cli_live_llm_preset_applies_defaults_before_workflow(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {
                name: os.getenv(name)
                for name in cli_module.LIVE_LLM_PRESET_DEFAULTS
            }
        )
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents", "--preset", "live-llm"])

    assert result.exit_code == 0
    assert observed_env == cli_module.LIVE_LLM_PRESET_DEFAULTS
    assert "# Report" in result.output


def test_cli_offline_preset_does_not_apply_live_defaults(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {
                name: os.getenv(name)
                for name in cli_module.LIVE_LLM_PRESET_DEFAULTS
            }
        )
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents", "--preset", "offline"])

    assert result.exit_code == 0
    assert observed_env == {
        name: None for name in cli_module.LIVE_LLM_PRESET_DEFAULTS
    }


def test_cli_rejects_unknown_preset_before_workflow(monkeypatch) -> None:
    def fail_if_called(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    monkeypatch.setattr(cli_module, "run_research", fail_if_called)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents", "--preset", "bad"])

    assert result.exit_code != 0
    assert "bad" in result.output
```

- [ ] **Step 2: Run new CLI integration tests to verify they fail**

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_live_llm_preset_applies_defaults_before_workflow tests/test_cli.py::test_cli_offline_preset_does_not_apply_live_defaults tests/test_cli.py::test_cli_rejects_unknown_preset_before_workflow -q
```

Expected: FAIL because `research()` does not accept `--preset` yet.

- [ ] **Step 3: Add the CLI option and apply preset before workflow**

Update the `research()` signature and body in `src/insight_graph/cli.py`:

```python
@app.command()
def research(
    query: str,
    preset: ResearchPreset = typer.Option(
        ResearchPreset.offline,
        "--preset",
        help="Runtime preset: offline or live-llm.",
    ),
) -> None:
    """Run a research workflow and print a Markdown report."""
    _apply_research_preset(preset)
    state = run_research(query)
    typer.echo(state.report_markdown or "")
```

- [ ] **Step 4: Run new CLI integration tests to verify they pass**

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_live_llm_preset_applies_defaults_before_workflow tests/test_cli.py::test_cli_offline_preset_does_not_apply_live_defaults tests/test_cli.py::test_cli_rejects_unknown_preset_before_workflow -q
```

Expected: PASS.

- [ ] **Step 5: Run all CLI tests**

Run:

```bash
python -m pytest tests/test_cli.py -q
```

Expected: all CLI tests pass.

- [ ] **Step 6: Run lint on changed Python files**

Run:

```bash
python -m ruff check src/insight_graph/cli.py tests/test_cli.py
```

Expected: `All checks passed!`.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add src/insight_graph/cli.py tests/test_cli.py
git commit -m "feat: add live llm cli preset"
```

---

### Task 3: Document Live LLM Preset

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README section**

Add this section after the existing LLM Reporter configuration section:

````markdown
### Live LLM Preset

The default CLI remains deterministic/offline:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

To enable the live pipeline with one explicit switch, configure your LLM endpoint and use `--preset live-llm`:

```bash
INSIGHT_GRAPH_LLM_API_KEY=sk-your-relay-key \
INSIGHT_GRAPH_LLM_BASE_URL=https://relay.example.com/v1 \
INSIGHT_GRAPH_LLM_MODEL=gpt-4o-mini \
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm
```

`live-llm` applies missing runtime defaults for DuckDuckGo search, relevance filtering, OpenAI-compatible relevance judging, LLM Analyst, and LLM Reporter. It does not permanently modify your environment and does not accept API keys as command-line arguments.
````

- [ ] **Step 2: Verify README contains the preset docs**

Run:

```bash
python -m pytest tests/test_cli.py -q
```

Expected: PASS. This is a smoke check that README changes did not affect CLI tests.

- [ ] **Step 3: Commit Task 3**

Run:

```bash
git add README.md
git commit -m "docs: document live llm preset"
```

---

### Task 4: Final Verification

**Files:**
- No code changes expected

- [ ] **Step 1: Run full test suite**

Run:

```bash
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Run full lint**

Run:

```bash
python -m ruff check .
```

Expected: `All checks passed!`.

- [ ] **Step 3: Run offline CLI smoke**

Run:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

Expected: report prints without needing LLM credentials or network access.

- [ ] **Step 4: Run live preset CLI smoke with fake workflow only if avoiding real network**

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_live_llm_preset_applies_defaults_before_workflow -q
```

Expected: PASS. This verifies preset wiring without real DuckDuckGo or LLM calls.

- [ ] **Step 5: Inspect final git state**

Run:

```bash
git status --short --branch
```

Expected: clean branch after all task commits.

---

## Self-Review Notes

- Spec coverage: the plan covers default offline behavior, `live-llm` runtime defaults, env precedence, CLI validation, no key-on-command-line behavior, tests without network, and README docs.
- Placeholder scan: no placeholder markers are present.
- Type consistency: `ResearchPreset`, `LIVE_LLM_PRESET_DEFAULTS`, and `_apply_research_preset()` are introduced in Task 1 and reused consistently in Task 2.
