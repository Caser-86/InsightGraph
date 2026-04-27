# API Job Status Constants Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize research job status strings and status sets used by create/list/detail/cancel/summary/prune/limit logic.

**Architecture:** Keep public API status values unchanged as strings. Define module-level constants in `src/insight_graph/api.py` for individual statuses and derived sets/lists, then replace duplicated inline sets and literals where they represent status logic.

**Tech Stack:** FastAPI, pytest, existing `tests/test_api.py` API tests.

---

### Task 1: Status Constant Contract Test

**Files:**
- Modify: `tests/test_api.py`
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Write failing constant test**

Add a test asserting:

```python
def test_research_job_status_constants_match_public_statuses() -> None:
    assert api_module._RESEARCH_JOB_STATUSES == (
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
    )
    assert api_module._ACTIVE_RESEARCH_JOB_STATUSES == {"queued", "running"}
    assert api_module._TERMINAL_RESEARCH_JOB_STATUSES == {
        "succeeded",
        "failed",
        "cancelled",
    }
```

- [ ] **Step 2: Run focused test**

Run: `python -m pytest tests/test_api.py::test_research_job_status_constants_match_public_statuses -q`

Expected: FAIL because the constants do not exist.

- [ ] **Step 3: Add constants**

In `src/insight_graph/api.py`, add module-level constants for individual status values plus `_RESEARCH_JOB_STATUSES`, `_ACTIVE_RESEARCH_JOB_STATUSES`, and `_TERMINAL_RESEARCH_JOB_STATUSES`.

- [ ] **Step 4: Run focused test again**

Run: `python -m pytest tests/test_api.py::test_research_job_status_constants_match_public_statuses -q`

Expected: PASS.

---

### Task 2: Replace Status Logic Duplicates

**Files:**
- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Replace status literals in logic**

Replace inline status sets/lists in `_queued_job_positions_locked()`, `_active_research_job_count_locked()`, `_job_queue_position_field()`, `_job_detail()`, `summarize_research_jobs()`, `cancel_research_job()`, `_run_research_job()`, and `_prune_finished_jobs_locked()` with the new constants. Keep externally visible JSON strings unchanged.

- [ ] **Step 2: Run API tests**

Run: `python -m pytest tests/test_api.py -q`

Expected: all API tests pass.

---

### Task 3: Verification And Commit

**Files:**
- Verify only, then commit all modified files.

- [ ] **Step 1: Run full tests**

Run: `python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run lint**

Run: `python -m ruff check .`

Expected: `All checks passed!`

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/superpowers/plans/2026-04-27-api-job-status-constants.md src/insight_graph/api.py tests/test_api.py
git commit -m "refactor: centralize research job statuses"
```

Expected: one commit containing constants, replacement refactor, tests, and this plan.

---

## Self-Review

- Spec coverage: public status values, active/terminal sets, and replacement of duplicated logic are covered.
- Placeholder scan: no TBD/TODO/implement-later placeholders remain.
- Type consistency: all status constants keep existing public string values unchanged.
