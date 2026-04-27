# API Jobs Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight `GET /research/jobs/summary` endpoint for current job status counts and active queued/running job overview.

**Architecture:** Reuse the existing in-memory `_JOBS` store under `_JOBS_LOCK`. Compute counts for every known status plus `total`; return only `queued_jobs` and `running_jobs` summaries, with no result payloads or error details.

**Tech Stack:** FastAPI, pytest, existing in-memory `ResearchJob` dataclass and fake executors in `tests/test_api.py`.

---

### Task 1: Summary Counts And Active Jobs

**Files:**
- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing summary test**

Add a test that creates one `queued`, one `running`, one `succeeded`, one `failed`, and one `cancelled` job, then asserts `GET /research/jobs/summary` returns:

```python
{
    "counts": {
        "total": 5,
        "queued": 1,
        "running": 1,
        "succeeded": 1,
        "failed": 1,
        "cancelled": 1,
    },
    "queued_jobs": [<queued summary with queue_position>],
    "running_jobs": [<running summary without queue_position>],
}
```

The test must assert `result`, `error`, and provider exception details are absent from the response.

- [ ] **Step 2: Run the focused test**

Run: `python -m pytest tests/test_api.py::test_get_research_jobs_summary_returns_counts_and_active_jobs -q`

Expected: FAIL because the endpoint does not exist.

- [ ] **Step 3: Implement the minimal endpoint**

Add `@app.get("/research/jobs/summary")` before `@app.get("/research/jobs/{job_id}")`. Under `_JOBS_LOCK`, compute counts, queued positions, `queued_jobs`, and `running_jobs`. Reuse `_job_summary()` so timing and queue position behavior stays consistent.

- [ ] **Step 4: Run the focused test again**

Run: `python -m pytest tests/test_api.py::test_get_research_jobs_summary_returns_counts_and_active_jobs -q`

Expected: PASS.

---

### Task 2: Empty Summary And Route Order


**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add empty summary and route-order tests**

Add tests that assert an empty store returns zero counts and empty active lists, and that `/research/jobs/summary` is not treated as a job ID by the detail route.

- [ ] **Step 2: Run focused summary tests**

Run: `python -m pytest tests/test_api.py::test_get_research_jobs_summary_returns_empty_counts tests/test_api.py::test_get_research_jobs_summary_route_is_not_job_detail -q`

Expected: PASS after Task 1 implementation.

---

### Task 3: Docs And Regression Checks

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Test: `tests/test_api.py`

- [ ] **Step 1: Update docs**

Document `GET /research/jobs/summary`, the counts object, and that only queued/running active summaries are included.

- [ ] **Step 2: Run API tests**

Run: `python -m pytest tests/test_api.py -q`

Expected: all API tests pass.

---

### Task 4: Full Verification And Commit

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
git add README.md docs/architecture.md docs/superpowers/plans/2026-04-27-api-jobs-summary.md src/insight_graph/api.py tests/test_api.py
git commit -m "feat: add research jobs summary endpoint"
```

Expected: one commit containing the endpoint, tests, docs, and this plan.

---

## Self-Review

- Spec coverage: status counts, queued/running active summaries, no result/error leakage, empty store, route order, docs, and verification are covered.
- Placeholder scan: no TBD/TODO/implement-later placeholders remain.
- Type consistency: endpoint name is `/research/jobs/summary`; response fields are `counts`, `queued_jobs`, and `running_jobs` everywhere.
