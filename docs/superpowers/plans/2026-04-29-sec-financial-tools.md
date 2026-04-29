# SEC Financial Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic SEC companyfacts evidence for simple financial metrics.

**Architecture:** Extend the existing SEC module with `sec_financials()`. It resolves the same known ticker/company targets, fetches SEC companyfacts JSON, extracts recent revenue/net income/assets facts, and returns one verified official evidence item. Planner and live presets expose it through an explicit `INSIGHT_GRAPH_USE_SEC_FINANCIALS` opt-in.

**Tech Stack:** Python 3.11+, SEC JSON fixtures in tests, pytest, ruff.

---

### Task 1: Add Simple SEC Financial Evidence

**Files:**
- Modify: `src/insight_graph/tools/sec_filings.py`
- Modify: `src/insight_graph/tools/__init__.py`
- Modify: `src/insight_graph/tools/registry.py`
- Modify: `src/insight_graph/agents/planner.py`
- Modify: `src/insight_graph/cli.py`
- Test: `tests/test_tools.py`
- Test: `tests/test_agents.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Add tests for `sec_financials()` mapping fake companyfacts JSON into verified evidence, ToolRegistry running `sec_financials`, Planner adding the tool when `INSIGHT_GRAPH_USE_SEC_FINANCIALS=1`, and `live-research` setting the env default.

- [ ] **Step 2: Verify RED**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py::test_sec_financials_maps_companyfacts tests/test_tools.py::test_registry_runs_sec_financials_tool tests/test_agents.py::test_planner_uses_sec_financials_when_enabled tests/test_cli.py::test_apply_live_research_preset_sets_network_defaults -v
```

Expected: FAIL because `sec_financials` is not implemented or registered.

- [ ] **Step 3: Implement `sec_financials()`**

Fetch `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`, pick recent USD facts for `Revenues`, `NetIncomeLoss`, and `Assets`, and build one verified `Evidence` snippet. If no known ticker or no facts exist, return empty list.

- [ ] **Step 4: Register and plan the tool**

Export `sec_financials`, add it to `ToolRegistry`, add `INSIGHT_GRAPH_USE_SEC_FINANCIALS` planner gating, and add the env to `live-research` defaults.

- [ ] **Step 5: Verify GREEN**

Run the same targeted pytest command. Expected: PASS.

- [ ] **Step 6: Full verification**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: tests pass, ruff passes, diff check has no whitespace errors.

---

## Self-Review

- Spec coverage: implements next-work queue item 8 without claiming full financial modeling.
- Placeholder scan: no placeholders remain.
- Type consistency: uses existing SEC target resolution and `Evidence` schema.
