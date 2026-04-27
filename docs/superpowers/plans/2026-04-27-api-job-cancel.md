# API Job Cancel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal safe API endpoint that cancels queued research jobs without attempting to interrupt running workflows.

**Architecture:** The existing FastAPI in-memory job store remains the source of truth. Cancellation is represented as a terminal `ResearchJob.status = "cancelled"`; `_run_research_job()` checks this state before marking a job running, so queued jobs can be skipped without tracking `Future` objects or killing threads.

**Tech Stack:** FastAPI, pytest, in-memory dataclass job store, existing fake executors in `tests/test_api.py`.

---

### Task 1: Queued Job Cancellation

**Files:**
- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add this test after `test_get_research_job_returns_404_for_unknown_job`:

```python
def test_cancel_research_job_cancels_queued_job(monkeypatch) -> None:
    fake_executor = FakeExecutor()
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    job_id = client.post("/research/jobs", json={"query": "Cancel me"}).json()["job_id"]

    response = client.post(f"/research/jobs/{job_id}/cancel")

    assert response.status_code == 200
    assert response.json() == {"job_id": job_id, "status": "cancelled"}
    assert client.get(f"/research/jobs/{job_id}").json() == {
        "job_id": job_id,
        "status": "cancelled",
    }

    fake_executor.run_next()

    assert observed_queries == []
    assert client.get(f"/research/jobs/{job_id}").json()["status"] == "cancelled"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_cancel_research_job_cancels_queued_job -q`

Expected: FAIL with HTTP `405 Method Not Allowed` because the cancel endpoint does not exist.

- [ ] **Step 3: Write minimal implementation**

In `src/insight_graph/api.py`, add `"cancelled"` as a terminal prunable status and add this endpoint before `@app.get("/research/jobs/{job_id}")`:

```python
@app.post("/research/jobs/{job_id}/cancel")
def cancel_research_job(job_id: str) -> dict[str, str]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        if job.status != "queued":
            raise HTTPException(
                status_code=409,
                detail="Only queued research jobs can be cancelled.",
            )
        job.status = "cancelled"
        _prune_finished_jobs_locked()
        return {"job_id": job.id, "status": job.status}
```

In `_run_research_job()`, replace the first locked block with:

```python
with _JOBS_LOCK:
    job = _JOBS[job_id]
    if job.status == "cancelled":
        return
    job.status = "running"
```

Update `_prune_finished_jobs_locked()` to include cancelled:

```python
if job.status in {"succeeded", "failed", "cancelled"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api.py::test_cancel_research_job_cancels_queued_job -q`

Expected: PASS.

---

### Task 2: Error States, List Visibility, And Docs

**Files:**
- Modify: `src/insight_graph/api.py`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Test: `tests/test_api.py`

- [ ] **Step 1: Add tests for non-queued and unknown jobs**

Add tests that assert:

```python
def test_cancel_research_job_returns_404_for_unknown_job() -> None:
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    response = client.post("/research/jobs/missing/cancel")

    assert response.status_code == 404
    assert response.json() == {"detail": "Research job not found."}


def test_cancel_research_job_rejects_running_or_finished_jobs(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    succeeded = client.post("/research/jobs", json={"query": "Succeeded"}).json()["job_id"]

    with api_module._JOBS_LOCK:
        api_module._JOBS[succeeded].status = "running"
    running_response = client.post(f"/research/jobs/{succeeded}/cancel")
    assert running_response.status_code == 409
    assert running_response.json() == {
        "detail": "Only queued research jobs can be cancelled."
    }

    with api_module._JOBS_LOCK:
        api_module._JOBS[succeeded].status = "succeeded"
    succeeded_response = client.post(f"/research/jobs/{succeeded}/cancel")
    assert succeeded_response.status_code == 409
    assert succeeded_response.json() == {
        "detail": "Only queued research jobs can be cancelled."
    }
```

- [ ] **Step 2: Run tests to verify behavior**

Run: `python -m pytest tests/test_api.py::test_cancel_research_job_returns_404_for_unknown_job tests/test_api.py::test_cancel_research_job_rejects_running_or_finished_jobs -q`

Expected: PASS after Task 1 implementation.

- [ ] **Step 3: Update list test to include cancelled state**

In `test_list_research_jobs_returns_summaries_newest_first`, cancel a queued job and assert its summary appears with `"status": "cancelled"` and no `result` or `error` fields.

- [ ] **Step 4: Update README**

Update the API MVP section to mention `POST /research/jobs/{job_id}/cancel`, and update status text to include `cancelled` with the rule: only queued jobs can be cancelled.

- [ ] **Step 5: Update architecture docs**

Update `docs/architecture.md` task tracking bullet to mention queued-only cancellation and cancelled terminal jobs.

---

### Task 3: Verification And Integration

**Files:**
- Verify only; no required edits.

- [ ] **Step 1: Run focused API tests**

Run: `python -m pytest tests/test_api.py -q`

Expected: all API tests pass.

- [ ] **Step 2: Run full tests**

Run: `python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 3: Run lint**

Run: `python -m ruff check .`

Expected: `All checks passed!`

- [ ] **Step 4: Commit**

Run:

```bash
git add README.md docs/architecture.md docs/superpowers/plans/2026-04-27-api-job-cancel.md src/insight_graph/api.py tests/test_api.py
git commit -m "feat: add research job cancellation"
```

Expected: one commit containing the cancel endpoint, tests, docs, and this plan.

---

## Self-Review

- Spec coverage: queued cancellation, skipped execution, 404, 409, list/detail visibility, docs, and verification are covered.
- Placeholder scan: no TBD/TODO/implement-later placeholders remain.
- Type consistency: endpoint returns `dict[str, str]`; job status strings match existing API style.
