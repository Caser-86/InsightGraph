# Live Research Preset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `live-research` runtime preset that explicitly enables the networked research path modeled after the reference project.

**Architecture:** Reuse the existing preset mechanism in `src/insight_graph/cli.py` and `scripts/run_research.py`. Keep `offline` deterministic, keep `live-llm` for LLM-heavy runs, and add `live-research` as the networked search/fetch/relevance preset with deterministic Analyst/Reporter unless users also opt into LLM behavior.

**Tech Stack:** Python 3.11+, Typer CLI, argparse script wrapper, pytest, ruff.

---

### Task 1: Add `live-research` Preset

**Files:**
- Modify: `src/insight_graph/cli.py`
- Modify: `scripts/run_research.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_run_research_script.py`

- [ ] **Step 1: Write the failing CLI preset test**

Add this test to `tests/test_cli.py` after the existing live preset tests:

```python
def test_apply_live_research_preset_sets_network_defaults(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    cli_module._apply_research_preset(cli_module.ResearchPreset.live_research)

    assert os.environ["INSIGHT_GRAPH_USE_WEB_SEARCH"] == "1"
    assert os.environ["INSIGHT_GRAPH_SEARCH_PROVIDER"] == "duckduckgo"
    assert os.environ["INSIGHT_GRAPH_SEARCH_LIMIT"] == "5"
    assert os.environ["INSIGHT_GRAPH_RELEVANCE_FILTER"] == "1"
    assert os.environ["INSIGHT_GRAPH_RELEVANCE_JUDGE"] == "deterministic"
    assert "INSIGHT_GRAPH_ANALYST_PROVIDER" not in os.environ
    assert "INSIGHT_GRAPH_REPORTER_PROVIDER" not in os.environ
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_cli.py::test_apply_live_research_preset_sets_network_defaults -v
```

Expected: FAIL because `ResearchPreset.live_research` does not exist.

- [ ] **Step 3: Implement the preset**

In `src/insight_graph/cli.py`, add enum value and defaults:

```python
class ResearchPreset(StrEnum):
    offline = "offline"
    live_llm = "live-llm"
    live_research = "live-research"


LIVE_RESEARCH_PRESET_DEFAULTS = {
    "INSIGHT_GRAPH_USE_WEB_SEARCH": "1",
    "INSIGHT_GRAPH_SEARCH_PROVIDER": "duckduckgo",
    "INSIGHT_GRAPH_SEARCH_LIMIT": "5",
    "INSIGHT_GRAPH_RELEVANCE_FILTER": "1",
    "INSIGHT_GRAPH_RELEVANCE_JUDGE": "deterministic",
}
```

Update `_apply_research_preset()` so `live-research` applies `LIVE_RESEARCH_PRESET_DEFAULTS` and `live-llm` keeps applying `LIVE_LLM_PRESET_DEFAULTS`.

- [ ] **Step 4: Verify GREEN**

Run the same targeted test. Expected: PASS.

- [ ] **Step 5: Add script wrapper test**

Add a test to `tests/test_run_research_script.py` proving `--preset live-research` applies the same defaults before `run_research_func` runs.

- [ ] **Step 6: Update docs**

Update `README.md`, `CHANGELOG.md`, and `docs/report-quality-roadmap.md` to document Phase 10 initial live-research preset.

- [ ] **Step 7: Verify**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_cli.py tests/test_run_research_script.py -v
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: tests pass, ruff passes, diff check has no whitespace errors.

- [ ] **Step 8: Commit**

```powershell
git add src/insight_graph/cli.py scripts/run_research.py tests/test_cli.py tests/test_run_research_script.py README.md CHANGELOG.md docs/report-quality-roadmap.md docs/superpowers/plans/2026-04-29-live-research-preset.md
git commit -m "feat(cli): add live research preset"
```

---

## Self-Review

- Spec coverage: covers the requested networked direction through an explicit live preset while preserving offline defaults.
- Placeholder scan: no placeholder tasks remain.
- Type consistency: preset names use `ResearchPreset.live_research` and CLI value `live-research` consistently.
