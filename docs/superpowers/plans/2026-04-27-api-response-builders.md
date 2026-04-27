# API Response Builders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract API job response assembly into focused helper functions without changing any public JSON response shape.

**Architecture:** Keep response payloads as plain dictionaries for minimal behavior risk. Add small private builders for create, detail, list, and summary responses that reuse the existing `_job_summary()` and `_job_detail()` helpers.

**Tech Stack:** FastAPI, pytest, existing in-memory API job tests in `tests/test_api.py`.

---

### Task 1: Create Response Builder Contract

**Files:**
- Modify: `tests/test_api.py`
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Write failing builder test**

Add a unit test that creates a `ResearchJob` instance directly and asserts `_job_create_response(job)` returns exactly `{"job_id": job.id, "status": "queued", "created_at": job.created_at}`.

- [ ] **Step 2: Run focused test**

Run: `python -m pytest tests/test_api.py::test_job_create_response_builder_returns_public_shape -q`

Expected: FAIL because `_job_create_response()` does not exist.

- [ ] **Step 3: Implement `_job_create_response()`**

Add a private helper in `src/insight_graph/api.py` and update `create_research_job()` to return it.

- [ ] **Step 4: Run focused test again**

Run: `python -m pytest tests/test_api.py::test_job_create_response_builder_returns_public_shape -q`

Expected: PASS.

---

### Task 2: List And Summary Response Builders

**Files:**
- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Extract list response builder**

Add `_jobs_list_response_locked()` that returns `{"jobs": summaries, "count": len(summaries)}` and update `list_research_jobs()` to call it inside `_JOBS_LOCK`.

- [ ] **Step 2: Extract summary response builder**

Add `_jobs_summary_response_locked()` that returns the existing summary response shape and update `summarize_research_jobs()` to call it inside `_JOBS_LOCK`.

- [ ] **Step 3: Run API tests**

Run: `python -m pytest tests/test_api.py -q`

Expected: all API tests pass with unchanged response shapes.

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
git add docs/superpowers/plans/2026-04-27-api-response-builders.md src/insight_graph/api.py tests/test_api.py
git commit -m "refactor: extract research job response builders"
```

Expected: one commit containing builder helpers, tests, and this plan.

---

## Self-Review

- Spec coverage: create/list/summary response assembly extraction and unchanged JSON shapes are covered.
- Placeholder scan: no TBD/TODO/implement-later placeholders remain.
- Type consistency: builders return dictionaries matching existing endpoint response shapes.
