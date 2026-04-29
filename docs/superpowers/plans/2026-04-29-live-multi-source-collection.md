# Live Multi-Source Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `live-research` preset collect from multiple networked sources instead of only the first enabled tool.

**Architecture:** Keep the legacy single-tool priority behavior for normal env combinations. Add `INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION=1` as an explicit switch used by `live-research`; when enabled, Planner returns all enabled live collection tools in stable order and Executor already runs each suggested tool.

**Tech Stack:** Python 3.11+, LangGraph state models, Typer CLI preset environment, pytest, ruff.

---

### Task 1: Enable Multi-Source Live Collection

**Files:**
- Modify: `src/insight_graph/cli.py`
- Modify: `src/insight_graph/agents/planner.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_agents.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write failing preset assertions**

Extend `tests/test_cli.py::test_apply_live_research_preset_sets_network_defaults`:

```python
assert os.environ["INSIGHT_GRAPH_USE_GITHUB_SEARCH"] == "1"
assert os.environ["INSIGHT_GRAPH_GITHUB_PROVIDER"] == "live"
assert os.environ["INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION"] == "1"
```

- [ ] **Step 2: Write failing Planner test**

Add:

```python
def test_planner_uses_multiple_live_sources_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["web_search", "github_search"]
```

- [ ] **Step 3: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_cli.py::test_apply_live_research_preset_sets_network_defaults tests/test_agents.py::test_planner_uses_multiple_live_sources_when_enabled -v
```

Expected: FAIL because the preset and Planner do not yet support multi-source live collection.

- [ ] **Step 4: Implement minimal code**

Add these defaults to `LIVE_RESEARCH_PRESET_DEFAULTS`:

```python
"INSIGHT_GRAPH_USE_GITHUB_SEARCH": "1",
"INSIGHT_GRAPH_GITHUB_PROVIDER": "live",
"INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION": "1",
```

Add `_collection_tool_names()` in `src/insight_graph/agents/planner.py` and use it for the collect subtask. Keep `_collection_tool_name()` unchanged for the legacy priority path.

- [ ] **Step 5: Verify GREEN**

Run the same targeted tests. Expected: PASS.

- [ ] **Step 6: Verify Executor behavior**

Add a test proving Executor runs both tools listed in one collect subtask. No production Executor change is needed because it already loops over `subtask.suggested_tools`.

- [ ] **Step 7: Update docs and changelog**

Update `README.md`, `docs/configuration.md`, `docs/report-quality-roadmap.md`, and `CHANGELOG.md` to describe web + GitHub live multi-source behavior.

- [ ] **Step 8: Verify full change**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: tests pass, ruff passes, diff check has no whitespace errors.

---

## Self-Review

- Spec coverage: covers the next live-research gap by making the live preset use multiple network-capable sources.
- Placeholder scan: no placeholders remain.
- Type consistency: env names match CLI defaults and Planner checks.
