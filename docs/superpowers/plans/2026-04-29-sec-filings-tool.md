# SEC Filings Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small SEC EDGAR filings source for public-company research.

**Architecture:** Add `sec_filings` as a normal InsightGraph tool returning verified `Evidence` from SEC submissions JSON. Keep it opt-in through `INSIGHT_GRAPH_USE_SEC_FILINGS`; `live-research` enables the env, while Planner only adds the tool when configured and when the request has a known ticker.

**Tech Stack:** Python 3.11+, urllib, Pydantic Evidence model, pytest, ruff.

---

### Task 1: Add SEC Filings Evidence Tool

**Files:**
- Create: `src/insight_graph/tools/sec_filings.py`
- Modify: `src/insight_graph/tools/__init__.py`
- Modify: `src/insight_graph/tools/registry.py`
- Modify: `src/insight_graph/agents/planner.py`
- Modify: `src/insight_graph/cli.py`
- Test: `tests/test_tools.py`
- Test: `tests/test_agents.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing tool tests**

Add tests proving `sec_filings("AAPL")` maps SEC submissions JSON into verified evidence and ToolRegistry can run `sec_filings`.

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py::test_tools_package_exports_sec_filings_callable -v
```

Expected: FAIL because `sec_filings` is not implemented.

- [ ] **Step 3: Implement minimal SEC tool**

Create `src/insight_graph/tools/sec_filings.py` with a known ticker-to-CIK map, SEC submissions JSON fetcher, and mapping for recent `10-K`, `10-Q`, `8-K`, and `S-1` filings.

- [ ] **Step 4: Register and export**

Export `sec_filings` from `tools/__init__.py` and register it in `ToolRegistry`.

- [ ] **Step 5: Add Planner opt-in**

Add `INSIGHT_GRAPH_USE_SEC_FILINGS` handling in Planner. In multi-source mode, append `sec_filings`; in single-source mode, return it after news search and before document reader.

- [ ] **Step 6: Enable in live-research preset**

Add `INSIGHT_GRAPH_USE_SEC_FILINGS=1` to `LIVE_RESEARCH_PRESET_DEFAULTS`.

- [ ] **Step 7: Verify full change**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: tests pass, ruff passes, diff check has no whitespace errors.

---

## Self-Review

- Spec coverage: adds the SEC/filings Phase 10 source without introducing persistence or financial modeling yet.
- Placeholder scan: no placeholders remain.
- Type consistency: tool name is consistently `sec_filings` and env is `INSIGHT_GRAPH_USE_SEC_FILINGS`.
