# Opt-In Rendered Fetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow `fetch_url` to use a rendered browser fetch path only when explicitly enabled.

**Architecture:** Keep default `fetch_text` behavior unchanged. Add an optional `render_page()` helper that imports Playwright lazily and a `fetch_url` env gate (`INSIGHT_GRAPH_FETCH_RENDERED`) that uses rendered HTML when available, falling back to bounded HTTP fetch if rendering cannot run.

**Tech Stack:** Python 3.11+, optional Playwright import, pytest, ruff.

---

### Task 1: Add Opt-In Rendered Fetch Hook

**Files:**
- Create: `src/insight_graph/tools/rendered_fetch.py`
- Modify: `src/insight_graph/tools/fetch_url.py`
- Test: `tests/test_fetch_url.py`

- [ ] **Step 1: Write failing test**

Add a test setting `INSIGHT_GRAPH_FETCH_RENDERED=1`, monkeypatching `render_page()` to return JavaScript-rendered HTML, and monkeypatching `fetch_text()` to fail if called. Expected evidence comes from rendered HTML.

- [ ] **Step 2: Verify RED**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_fetch_url.py::test_fetch_url_uses_rendered_fetch_when_enabled -v
```

Expected: FAIL because `fetch_url` currently always calls `fetch_text()`.

- [ ] **Step 3: Implement optional renderer**

Add `render_page(url, timeout=10.0)` with lazy `playwright.sync_api` import and return `FetchedPage` from rendered HTML. Raise `FetchError` when Playwright is unavailable or navigation fails.

- [ ] **Step 4: Wire env gate**

In `fetch_url`, call `render_page()` only when `INSIGHT_GRAPH_FETCH_RENDERED` is truthy. If rendered fetch raises `FetchError`, fall back to `fetch_text()` to keep opt-in demos robust.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_fetch_url.py::test_fetch_url_uses_rendered_fetch_when_enabled -v
```

Expected: PASS.

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

- Spec coverage: implements next-work queue item 7 without adding Playwright as a required dependency.
- Placeholder scan: no placeholders remain.
- Type consistency: uses existing `FetchedPage` and `FetchError` types.
