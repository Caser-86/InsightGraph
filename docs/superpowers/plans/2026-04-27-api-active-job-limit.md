# API Active Job Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent unbounded in-memory active research job growth by rejecting new jobs when `queued + running` reaches a configurable cap.

**Architecture:** Add `_MAX_ACTIVE_RESEARCH_JOBS` and enforce it inside the existing `_JOBS_LOCK` block before creating a new job. Terminal jobs (`succeeded`, `failed`, `cancelled`) remain controlled by the existing terminal retention pruning and do not count toward the active cap.

**Tech Stack:** FastAPI, pytest, existing in-memory `ResearchJob` dataclass and fake executors in `tests/test_api.py`.

---

### Task 1: Reject New Jobs At Active Limit

**Files:**
- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing limit test**

Add a test that sets `_MAX_ACTIVE_RESEARCH_JOBS = 2`, uses `FakeExecutor`, creates two queued jobs, then asserts the third `POST /research/jobs` returns `429` with safe detail `Too many active research jobs.` and does not submit a third executor task.

- [ ] **Step 2: Run the focused test**

Run: `python -m pytest tests/test_api.py::test_create_research_job_rejects_when_active_job_limit_reached -q`

Expected: FAIL because the API currently accepts the third queued job.

- [ ] **Step 3: Implement minimal active guard**

Add `_MAX_ACTIVE_RESEARCH_JOBS = 100` and helper `_active_research_job_count_locked()` counting only `queued` and `running`. In `create_research_job()`, before incrementing `_NEXT_JOB_SEQUENCE`, raise `HTTPException(status_code=429, detail="Too many active research jobs.")` when the active count is at or above the cap.

- [ ] **Step 4: Run the focused test again**

Run: `python -m pytest tests/test_api.py::test_create_research_job_rejects_when_active_job_limit_reached -q`

Expected: PASS.

---

### Task 2: Terminal Jobs Do Not Count

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add terminal exclusion test**

Add a test that sets `_MAX_ACTIVE_RESEARCH_JOBS = 1`, creates one immediate succeeded job, then creates another job successfully. Repeat for a cancelled queued job to prove cancelled jobs no longer count.

- [ ] **Step 2: Run focused test**

Run: `python -m pytest tests/test_api.py::test_create_research_job_active_limit_ignores_terminal_jobs -q`

Expected: PASS after Task 1 implementation.

---

### Task 3: Summary And Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Test: `tests/test_api.py`

- [ ] **Step 1: Update summary test**

Update `test_get_research_jobs_summary_returns_counts_and_active_jobs` to assert `active_limit` and `active_count` are present. `active_count` should equal queued plus running; `active_limit` should equal `_MAX_ACTIVE_RESEARCH_JOBS`.

- [ ] **Step 2: Implement summary fields**

In `summarize_research_jobs()`, include `active_count` and `active_limit` at the top level.

- [ ] **Step 3: Update docs**

Document that new job creation returns `429` once `queued + running` reaches the active cap, and that terminal jobs do not count toward this cap.

- [ ] **Step 4: Run API tests**

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
git add README.md docs/architecture.md docs/superpowers/plans/2026-04-27-api-active-job-limit.md src/insight_graph/api.py tests/test_api.py
git commit -m "feat: limit active research jobs"
```

Expected: one commit containing the active limit guard, tests, docs, and this plan.

---

## Self-Review

- Spec coverage: queued+running cap, 429 response, no executor submission after rejection, terminal exclusion, summary visibility, docs, and verification are covered.
- Placeholder scan: no TBD/TODO/implement-later placeholders remain.
- Type consistency: `active_count`, `active_limit`, and `_MAX_ACTIVE_RESEARCH_JOBS` are named consistently.
