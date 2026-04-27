# API Job Queue Position Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add queue position metadata for queued research jobs so API clients can show where a job sits in the single-worker in-memory queue.

**Architecture:** Keep queue position as derived response metadata, not stored state. Compute it under `_JOBS_LOCK` from queued jobs sorted by `created_order`; only queued jobs include `queue_position`, and running/terminal jobs omit it.

**Tech Stack:** FastAPI, pytest, existing in-memory job dataclass and fake executors in `tests/test_api.py`.

---

### Task 1: Queue Position For Queued Detail Responses

**Files:**
- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write a failing detail test**

Add a test that creates three queued jobs with `FakeExecutor`, marks the middle one `running`, and asserts the first and third queued jobs have `queue_position` values `1` and `2` in detail responses while the running job omits `queue_position`.

- [ ] **Step 2: Run the focused test**

Run: `python -m pytest tests/test_api.py::test_research_job_detail_includes_queue_position_for_queued_jobs -q`

Expected: FAIL because detail responses do not include `queue_position`.

- [ ] **Step 3: Implement minimal queue position support**

Add a helper that computes queued job positions while `_JOBS_LOCK` is held, and pass the queued position into `_job_detail()` when serving detail responses.

- [ ] **Step 4: Run the focused test again**

Run: `python -m pytest tests/test_api.py::test_research_job_detail_includes_queue_position_for_queued_jobs -q`

Expected: PASS.

---

### Task 2: Queue Position In List Responses

**Files:**
- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Update list test expectations**

Update `test_list_research_jobs_returns_summaries_newest_first` so the queued summary includes `queue_position: 1`, while running, succeeded, failed, and cancelled summaries omit `queue_position`.

- [ ] **Step 2: Run list test**

Run: `python -m pytest tests/test_api.py::test_list_research_jobs_returns_summaries_newest_first -q`

Expected: FAIL until list summaries include queue positions.

- [ ] **Step 3: Implement list queue positions**

Compute queued positions once in `list_research_jobs()` and pass them into `_job_summary()` for each job.

- [ ] **Step 4: Run list test again**

Run: `python -m pytest tests/test_api.py::test_list_research_jobs_returns_summaries_newest_first -q`

Expected: PASS.

---

### Task 3: Docs And Regression Checks

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Test: `tests/test_api.py`

- [ ] **Step 1: Update docs**

Mention that queued jobs include `queue_position`, and that the value is derived from current in-memory queued jobs and omitted for running/terminal jobs.

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
git add README.md docs/architecture.md docs/superpowers/plans/2026-04-27-api-job-queue-position.md src/insight_graph/api.py tests/test_api.py
git commit -m "feat: add research job queue positions"
```

Expected: one commit containing queue position metadata, tests, docs, and this plan.

---

## Self-Review

- Spec coverage: queued detail/list queue positions, omission for non-queued jobs, docs, and verification are covered.
- Placeholder scan: no TBD/TODO/implement-later placeholders remain.
- Type consistency: response field name is `queue_position` everywhere and uses 1-based integers.
