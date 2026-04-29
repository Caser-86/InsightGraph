# SEC Filings Precision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SEC filings collection trigger only for known public-company targets and accept common company names, not only tickers.

**Architecture:** Keep the SEC source as a small opt-in tool. Add shared ticker resolution in `sec_filings.py`, then have Planner call the same detector before adding `sec_filings` to single-source or multi-source collection.

**Tech Stack:** Python 3.11+, regex, pytest, ruff.

---

### Task 1: Add SEC Target Detection

**Files:**
- Modify: `src/insight_graph/tools/sec_filings.py`
- Modify: `src/insight_graph/agents/planner.py`
- Test: `tests/test_tools.py`
- Test: `tests/test_agents.py`

- [ ] **Step 1: Write failing tests**

Add tests proving `sec_filings("Analyze Apple filings")` resolves AAPL and Planner skips `sec_filings` for non-public-company requests even when `INSIGHT_GRAPH_USE_SEC_FILINGS=1`.

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py::test_sec_filings_accepts_company_name_alias tests/test_agents.py::test_planner_skips_sec_filings_without_public_company_target -v
```

Expected: FAIL because company aliases are not recognized and Planner adds SEC unconditionally in multi-source mode.

- [ ] **Step 3: Implement shared resolver**

Add `resolve_sec_ticker()` and `has_sec_filing_target()` in `sec_filings.py`. Resolve known tickers first, then company name aliases such as Apple, Microsoft, Alphabet/Google, Amazon, Meta, Nvidia, and Tesla.

- [ ] **Step 4: Gate Planner SEC tool selection**

Pass the user request into `_collection_tool_names()` and `_collection_tool_name()`. Add `sec_filings` only when the env flag is truthy and `has_sec_filing_target(user_request)` is true.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py::test_sec_filings_accepts_company_name_alias tests/test_agents.py::test_planner_adds_sec_filings_to_multi_source_for_public_company_name tests/test_agents.py::test_planner_skips_sec_filings_without_public_company_target -v
```

Expected: PASS.

- [ ] **Step 6: Full verification**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: tests pass, ruff passes, diff check has no whitespace errors.

---

## Self-Review

- Spec coverage: improves SEC source precision without adding new providers or network defaults.
- Placeholder scan: no placeholders remain.
- Type consistency: detector names are consistent between tool and Planner.
