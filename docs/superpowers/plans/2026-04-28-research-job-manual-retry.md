# Research Job Manual Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual retry endpoint that creates a new queued research job from a failed or cancelled source job.

**Architecture:** Keep retry orchestration in `research_jobs.py` service helpers. The API endpoint reuses the same background scheduling path as normal job creation; storage backends require no schema changes because retry creates a normal new job.

**Tech Stack:** Python 3.11+, FastAPI, pytest, existing research job service/backend modules.

---

## File Structure

- Modify: `src/insight_graph/research_jobs.py`
  - Add `retry_research_job(job_id, created_at)` service helper.
- Modify: `src/insight_graph/api.py`
  - Add `POST /research/jobs/{job_id}/retry`, response examples, and scheduling.
- Modify: `tests/test_research_jobs.py`
  - Cover service helper success/failure for failed/cancelled/invalid statuses and memory/sqlite contract.
- Modify: `tests/test_api.py`
  - Cover endpoint response, scheduling, 404/409/429.
- Modify: `docs/research-jobs-api.md`
  - Document retry endpoint.
- Modify: `docs/research-job-repository-contract.md`
  - Document retry creates a new job and leaves source unchanged.

## Task 1: Add Service Retry Helper

**Files:**
- Modify: `src/insight_graph/research_jobs.py`
- Modify: `tests/test_research_jobs.py`

- [ ] **Step 1: Write failing service tests**

Add to `tests/test_research_jobs.py`:

```python
def test_retry_research_job_clones_failed_job_as_new_queued_job() -> None:
    source = jobs_module.ResearchJob(
        id="failed-job",
        query="Retry me",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="failed",
        finished_at="2026-04-28T10:00:01Z",
        error="Research workflow failed.",
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    retried = jobs_module.retry_research_job(
        "failed-job",
        created_at="2026-04-28T10:00:02Z",
    )

    assert retried["status"] == "queued"
    assert retried["job_id"] != "failed-job"
    retry_record = jobs_module.get_research_job_record(retried["job_id"])
    assert retry_record is not None
    assert retry_record.query == source.query
    assert retry_record.preset == source.preset
    assert retry_record.created_order == 2
    assert jobs_module.get_research_job_record("failed-job") == source


def test_retry_research_job_clones_cancelled_job_as_new_queued_job() -> None:
    source = jobs_module.ResearchJob(
        id="cancelled-job",
        query="Retry cancelled",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="cancelled",
        finished_at="2026-04-28T10:00:01Z",
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    retried = jobs_module.retry_research_job(
        "cancelled-job",
        created_at="2026-04-28T10:00:02Z",
    )

    assert retried["status"] == "queued"
    assert retried["job_id"] != "cancelled-job"


@pytest.mark.parametrize("status", ["queued", "running", "succeeded"])
def test_retry_research_job_rejects_non_retryable_statuses(status: str) -> None:
    source = jobs_module.ResearchJob(
        id="job-1",
        query="Not retryable",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status=status,
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    with pytest.raises(jobs_module.HTTPException) as exc_info:
        jobs_module.retry_research_job(
            "job-1",
            created_at="2026-04-28T10:00:02Z",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Only failed or cancelled research jobs can be retried."


def test_retry_research_job_returns_404_for_missing_job() -> None:
    jobs_module.reset_research_jobs_state()

    with pytest.raises(jobs_module.HTTPException) as exc_info:
        jobs_module.retry_research_job(
            "missing",
            created_at="2026-04-28T10:00:02Z",
        )

    assert exc_info.value.status_code == 404
```

- [ ] **Step 2: Run service retry tests to verify RED**

Run: `python -m pytest tests/test_research_jobs.py::test_retry_research_job_clones_failed_job_as_new_queued_job -v`

Expected: FAIL with missing `retry_research_job`.

- [ ] **Step 3: Implement service helper**

Add constant:

```python
RETRYABLE_RESEARCH_JOB_STATUSES = {
    RESEARCH_JOB_STATUS_FAILED,
    RESEARCH_JOB_STATUS_CANCELLED,
}
```

Add helper after `create_research_job()`:

```python
def retry_research_job(job_id: str, created_at: str) -> dict[str, str]:
    with _JOBS_LOCK:
        source = _get_research_job_locked(job_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        if source.status not in RETRYABLE_RESEARCH_JOB_STATUSES:
            raise HTTPException(
                status_code=409,
                detail="Only failed or cancelled research jobs can be retried.",
            )
    return create_research_job(
        query=source.query,
        preset=source.preset,
        created_at=created_at,
    )
```

- [ ] **Step 4: Run service retry tests to verify GREEN**

Run: `python -m pytest tests/test_research_jobs.py::test_retry_research_job_clones_failed_job_as_new_queued_job tests/test_research_jobs.py::test_retry_research_job_clones_cancelled_job_as_new_queued_job tests/test_research_jobs.py::test_retry_research_job_rejects_non_retryable_statuses tests/test_research_jobs.py::test_retry_research_job_returns_404_for_missing_job -v`

Expected: PASS.

## Task 2: Add API Endpoint

**Files:**
- Modify: `src/insight_graph/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Add to `tests/test_api.py`:

```python
def test_retry_research_job_endpoint_creates_and_schedules_new_job(monkeypatch) -> None:
    reset_jobs_state()
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    source = jobs_module.ResearchJob(
        id="failed-job",
        query="Retry via API",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="failed",
        finished_at="2026-04-28T10:00:01Z",
        error="Research workflow failed.",
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    response = TestClient(api_module.app).post("/research/jobs/failed-job/retry")

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["job_id"] != "failed-job"
    assert fake_executor.submissions == [(api_module._run_research_job, (payload["job_id"],))]


def test_retry_research_job_endpoint_rejects_running_job() -> None:
    reset_jobs_state()
    source = jobs_module.ResearchJob(
        id="running-job",
        query="Running",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="running",
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    response = TestClient(api_module.app).post("/research/jobs/running-job/retry")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Only failed or cancelled research jobs can be retried."
    }
```

- [ ] **Step 2: Run API retry test to verify RED**

Run: `python -m pytest tests/test_api.py::test_retry_research_job_endpoint_creates_and_schedules_new_job -v`

Expected: FAIL with 404 route not found.

- [ ] **Step 3: Add API route**

Import service helper:

```python
from insight_graph.research_jobs import (
    retry_research_job as retry_research_job_record,
)
```

Add response example:

```python
_RESEARCH_JOB_RETRY_CONFLICT_RESPONSE = {
    "description": "Only failed or cancelled research jobs can be retried.",
    "content": {
        "application/json": {
            "example": {"detail": "Only failed or cancelled research jobs can be retried."}
        }
    },
}
```

Add endpoint after cancel route:

```python
@router.post(
    "/research/jobs/{job_id}/retry",
    status_code=202,
    response_model=ResearchJobCreateResponse,
    response_model_exclude_none=True,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Retry failed or cancelled research job",
    description="Create a new queued job from a failed or cancelled research job.",
    responses={
        202: {"content": {"application/json": {"example": _RESEARCH_JOB_CREATE_EXAMPLE}}},
        404: _RESEARCH_JOB_NOT_FOUND_RESPONSE,
        409: _RESEARCH_JOB_RETRY_CONFLICT_RESPONSE,
        429: _TOO_MANY_ACTIVE_RESEARCH_JOBS_RESPONSE,
        500: _RESEARCH_JOB_STORE_FAILED_RESPONSE,
    },
)
def retry_research_job(job_id: str) -> dict[str, str]:
    response = retry_research_job_record(
        job_id=job_id,
        created_at=_current_utc_timestamp(),
    )
    _JOB_EXECUTOR.submit(_run_research_job, response["job_id"])
    return response
```

- [ ] **Step 4: Run API retry tests to verify GREEN**

Run: `python -m pytest tests/test_api.py::test_retry_research_job_endpoint_creates_and_schedules_new_job tests/test_api.py::test_retry_research_job_endpoint_rejects_running_job -v`

Expected: PASS.

## Task 3: Add Contract Tests and Docs

**Files:**
- Modify: `tests/test_research_jobs.py`
- Modify: `tests/test_api.py`
- Modify: `docs/research-jobs-api.md`
- Modify: `docs/research-job-repository-contract.md`

- [ ] **Step 1: Add backend contract retry test**

Add to `tests/test_research_jobs.py`:

```python
def test_research_jobs_backend_contract_retry_failed_job(research_jobs_backend) -> None:
    source = jobs_module.ResearchJob(
        id="failed-job",
        query="Contract retry",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="failed",
        finished_at="2026-04-28T10:00:01Z",
        error="Research workflow failed.",
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    retried = jobs_module.retry_research_job(
        "failed-job",
        created_at="2026-04-28T10:00:02Z",
    )

    assert retried["status"] == "queued"
    retry_record = jobs_module.get_research_job_record(retried["job_id"])
    assert retry_record is not None
    assert retry_record.query == "Contract retry"
```

- [ ] **Step 2: Add active cap API retry test**

Add to `tests/test_api.py`:

```python
def test_retry_research_job_endpoint_respects_active_cap() -> None:
    reset_jobs_state()
    source = jobs_module.ResearchJob(
        id="failed-job",
        query="Retry over cap",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="failed",
        finished_at="2026-04-28T10:00:01Z",
        error="Research workflow failed.",
    )
    active = jobs_module.ResearchJob(
        id="active-job",
        query="Active",
        preset=api_module.ResearchPreset.offline,
        created_order=2,
        created_at="2026-04-28T10:00:02Z",
    )
    jobs_module.reset_research_jobs_state(
        next_job_sequence=2,
        active_limit=1,
        jobs=[source, active],
    )

    response = TestClient(api_module.app).post("/research/jobs/failed-job/retry")

    assert response.status_code == 429
    assert response.json() == {"detail": "Too many active research jobs."}
```

- [ ] **Step 3: Update docs**

Add to `docs/research-jobs-api.md` endpoint list:

```markdown
- `POST /research/jobs/{job_id}/retry` creates a new queued job from a failed or cancelled job.
```

Add section after Cancel:

```markdown
## Retry

```bash
curl -X POST http://127.0.0.1:8000/research/jobs/job-123/retry
```

Only `failed` and `cancelled` jobs are retryable. Retry creates a new queued job with the same query and preset; the source job is unchanged.

Non-retryable jobs return `409`:

```json
{"detail":"Only failed or cancelled research jobs can be retried."}
```
```

Add to `docs/research-job-repository-contract.md` stable contract:

```markdown
- Manual retry creates a new queued job from a failed or cancelled source job; the source job is not mutated.
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_research_jobs.py tests/test_api.py
python -m ruff check .
git diff --check
```

Expected: PASS / no lint / no whitespace errors.

## Final Verification

Run:

```bash
python -m pytest
python -m ruff check .
git status --short --branch
```

Expected:

- `pytest`: all tests pass.
- `ruff`: no issues.
- `git status`: clean after commit.
