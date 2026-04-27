# Research Job Repository Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move research job state management from `src/insight_graph/api.py` into `src/insight_graph/research_jobs.py` without changing runtime API behavior.

**Architecture:** Create one in-process repository module that owns job state, persistence, rollback, response builders, pruning, and worker state transitions. Keep `api.py` responsible for FastAPI wiring, OpenAPI metadata, request/response models, executor submission, timestamp creation, and `run_research()` orchestration.

**Tech Stack:** Python 3.11+, FastAPI `HTTPException`, dataclasses, `threading.Lock`, pytest, ruff.

---

## File Structure

- Create `src/insight_graph/research_jobs.py`: repository module for job dataclass, state constants, in-memory state, JSON persistence integration, response builders, repository actions, and worker transition helpers.
- Modify `src/insight_graph/api.py`: remove job repository internals, import repository functions/constants, keep route decorators and workflow execution.
- Create `tests/test_research_jobs.py`: repository-level tests migrated from private `api_module` internals.
- Modify `tests/test_api.py`: keep HTTP/OpenAPI/workflow tests; import `insight_graph.research_jobs as jobs_module` for route setup that needs controlled job state.

## Public Repository API To Implement

`src/insight_graph/research_jobs.py` must expose these names:

```python
RESEARCH_JOB_STATUS_QUEUED
RESEARCH_JOB_STATUS_RUNNING
RESEARCH_JOB_STATUS_SUCCEEDED
RESEARCH_JOB_STATUS_FAILED
RESEARCH_JOB_STATUS_CANCELLED
RESEARCH_JOB_STATUSES
ACTIVE_RESEARCH_JOB_STATUSES
TERMINAL_RESEARCH_JOB_STATUSES
ResearchJob
ResearchJobStatus
initialize_research_jobs
create_research_job
list_research_jobs
summarize_research_jobs
cancel_research_job
get_research_job
mark_research_job_running
mark_research_job_failed
mark_research_job_succeeded
```

Private repository internals may keep leading underscores:

```python
_JOBS_LOCK
_MAX_RESEARCH_JOBS
_MAX_ACTIVE_RESEARCH_JOBS
_NEXT_JOB_SEQUENCE
_JOBS
_RESEARCH_JOBS_PATH
_persist_research_jobs_locked
_research_jobs_state_snapshot_locked
_restore_research_jobs_state_locked
_prune_finished_jobs_locked
```

Do not re-export old private names from `api.py`.

## Task 1: Add Repository Tests For Core State Behavior

**Files:**
- Create: `tests/test_research_jobs.py`

- [ ] **Step 1: Create repository test file with status, initialization, and response-builder tests**

Create `tests/test_research_jobs.py` with:

```python
import pytest

import insight_graph.research_jobs as jobs_module
from insight_graph.cli import ResearchPreset
from insight_graph.research_jobs_store import ResearchJobsStoreError


def reset_jobs_state() -> None:
    jobs_module._NEXT_JOB_SEQUENCE = 0
    jobs_module._JOBS.clear()
    jobs_module._RESEARCH_JOBS_PATH = None
    jobs_module._MAX_RESEARCH_JOBS = 100
    jobs_module._MAX_ACTIVE_RESEARCH_JOBS = 100


def test_research_job_status_constants_match_public_statuses() -> None:
    assert jobs_module.RESEARCH_JOB_STATUSES == (
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
    )
    assert jobs_module.ACTIVE_RESEARCH_JOB_STATUSES == {"queued", "running"}
    assert jobs_module.TERMINAL_RESEARCH_JOB_STATUSES == {
        "succeeded",
        "failed",
        "cancelled",
    }


def test_job_create_response_builder_returns_public_shape() -> None:
    reset_jobs_state()
    job = jobs_module.ResearchJob(
        id="job-1",
        query="Compare Cursor",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T10:00:00Z",
    )

    assert jobs_module._job_create_response(job) == {
        "job_id": "job-1",
        "status": "queued",
        "created_at": "2026-04-27T10:00:00Z",
    }


def test_initialize_research_jobs_noops_without_store_path() -> None:
    reset_jobs_state()
    jobs_module._NEXT_JOB_SEQUENCE = 8
    jobs_module._JOBS["existing"] = jobs_module.ResearchJob(
        id="existing",
        query="Existing",
        preset=ResearchPreset.offline,
        created_order=8,
        created_at="2026-04-27T20:00:00Z",
    )

    jobs_module.initialize_research_jobs(restart_timestamp="2026-04-27T20:00:01Z")

    assert jobs_module._NEXT_JOB_SEQUENCE == 8
    assert set(jobs_module._JOBS) == {"existing"}


def test_initialize_research_jobs_loads_configured_store(tmp_path) -> None:
    reset_jobs_state()
    store_path = tmp_path / "jobs.json"
    store_path.write_text(
        """
{
  "jobs": [
    {
      "created_at": "2026-04-27T20:00:00Z",
      "created_order": 4,
      "error": null,
      "finished_at": "2026-04-27T20:00:02Z",
      "id": "job-4",
      "preset": "offline",
      "query": "Persisted",
      "result": {"report_markdown": "# Report"},
      "started_at": "2026-04-27T20:00:01Z",
      "status": "succeeded"
    }
  ],
  "next_job_sequence": 4
}
""".strip(),
        encoding="utf-8",
    )
    jobs_module._RESEARCH_JOBS_PATH = store_path

    jobs_module.initialize_research_jobs(restart_timestamp="2026-04-27T21:00:00Z")

    assert jobs_module._NEXT_JOB_SEQUENCE == 4
    assert jobs_module._JOBS["job-4"].status == "succeeded"
    assert jobs_module._JOBS["job-4"].result == {"report_markdown": "# Report"}


def test_initialize_research_jobs_marks_unfinished_jobs_failed(tmp_path) -> None:
    reset_jobs_state()
    store_path = tmp_path / "jobs.json"
    store_path.write_text(
        """
{
  "jobs": [
    {
      "created_at": "2026-04-27T20:00:00Z",
      "created_order": 1,
      "error": null,
      "finished_at": null,
      "id": "job-1",
      "preset": "offline",
      "query": "Queued",
      "result": null,
      "started_at": null,
      "status": "queued"
    }
  ],
  "next_job_sequence": 1
}
""".strip(),
        encoding="utf-8",
    )
    jobs_module._RESEARCH_JOBS_PATH = store_path

    jobs_module.initialize_research_jobs(restart_timestamp="2026-04-27T21:00:00Z")

    job = jobs_module._JOBS["job-1"]
    assert job.status == "failed"
    assert job.finished_at == "2026-04-27T21:00:00Z"
    assert job.error == "Research job did not complete before server restart."


def test_initialize_research_jobs_fails_closed_for_bad_store(tmp_path) -> None:
    reset_jobs_state()
    store_path = tmp_path / "jobs.json"
    store_path.write_text("{bad-json", encoding="utf-8")
    jobs_module._RESEARCH_JOBS_PATH = store_path

    with pytest.raises(ResearchJobsStoreError):
        jobs_module.initialize_research_jobs(restart_timestamp="2026-04-27T21:00:00Z")


def test_research_jobs_state_snapshot_restores_jobs_and_sequence() -> None:
    reset_jobs_state()
    original = jobs_module.ResearchJob(
        id="job-1",
        query="Original",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    jobs_module._NEXT_JOB_SEQUENCE = 1
    jobs_module._JOBS[original.id] = original
    snapshot = jobs_module._research_jobs_state_snapshot_locked()

    jobs_module._NEXT_JOB_SEQUENCE = 2
    jobs_module._JOBS.clear()

    jobs_module._restore_research_jobs_state_locked(snapshot)

    assert jobs_module._NEXT_JOB_SEQUENCE == 1
    assert jobs_module._JOBS == {"job-1": original}
```

- [ ] **Step 2: Run repository tests and verify red**

Run:

```bash
python -m pytest tests/test_research_jobs.py -q
```

Expected: FAIL because `insight_graph.research_jobs` does not exist.

## Task 2: Create Repository Module By Moving Existing Internals

**Files:**
- Create: `src/insight_graph/research_jobs.py`
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Create `src/insight_graph/research_jobs.py` with moved code**

Create `src/insight_graph/research_jobs.py` with this structure. Copy the current implementations from `api.py` and rename public constants by dropping the leading underscore:

```python
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException

from insight_graph.cli import ResearchPreset
from insight_graph.research_jobs_store import (
    ResearchJobsStoreError,
    load_research_jobs,
    research_jobs_path_from_env,
    save_research_jobs,
)

RESEARCH_JOB_STATUS_QUEUED = "queued"
RESEARCH_JOB_STATUS_RUNNING = "running"
RESEARCH_JOB_STATUS_SUCCEEDED = "succeeded"
RESEARCH_JOB_STATUS_FAILED = "failed"
RESEARCH_JOB_STATUS_CANCELLED = "cancelled"
RESEARCH_JOB_STATUSES = (
    RESEARCH_JOB_STATUS_QUEUED,
    RESEARCH_JOB_STATUS_RUNNING,
    RESEARCH_JOB_STATUS_SUCCEEDED,
    RESEARCH_JOB_STATUS_FAILED,
    RESEARCH_JOB_STATUS_CANCELLED,
)
ResearchJobStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
]
ACTIVE_RESEARCH_JOB_STATUSES = {
    RESEARCH_JOB_STATUS_QUEUED,
    RESEARCH_JOB_STATUS_RUNNING,
}
TERMINAL_RESEARCH_JOB_STATUSES = {
    RESEARCH_JOB_STATUS_SUCCEEDED,
    RESEARCH_JOB_STATUS_FAILED,
    RESEARCH_JOB_STATUS_CANCELLED,
}
_JOBS_LOCK = Lock()
_MAX_RESEARCH_JOBS = 100
_MAX_ACTIVE_RESEARCH_JOBS = 100
_NEXT_JOB_SEQUENCE = 0
_JOBS: dict[str, "ResearchJob"] = {}
_RESEARCH_JOBS_PATH: Path | None = research_jobs_path_from_env()


@dataclass
class ResearchJob:
    id: str
    query: str
    preset: ResearchPreset
    created_order: int
    created_at: str
    status: str = RESEARCH_JOB_STATUS_QUEUED
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
```

Then move these functions from `api.py` into `research_jobs.py`, replacing old constant names with the new public names:

```python
_research_job_from_store
initialize_research_jobs
ResearchJobsStateSnapshot
_research_jobs_state_snapshot_locked
_restore_research_jobs_state_locked
_persist_research_jobs_locked
_persist_research_jobs_or_500_locked
_job_timing_fields
_queued_job_positions_locked
_active_research_job_count_locked
_job_queue_position_field
_job_summary
_job_create_response
_job_detail
_jobs_list_response_locked
_jobs_summary_response_locked
_persist_research_jobs_best_effort_locked
_mark_research_job_running_locked
_mark_research_job_failed_locked
_mark_research_job_succeeded_locked
_prune_finished_jobs_locked
```

- [ ] **Step 2: Add public wrapper functions in `research_jobs.py`**

Append these functions after the moved private helpers:

```python
def create_research_job(
    query: str,
    preset: ResearchPreset,
    created_at: str,
) -> dict[str, str]:
    global _NEXT_JOB_SEQUENCE

    with _JOBS_LOCK:
        if _active_research_job_count_locked() >= _MAX_ACTIVE_RESEARCH_JOBS:
            raise HTTPException(
                status_code=429,
                detail="Too many active research jobs.",
            )
        snapshot = _research_jobs_state_snapshot_locked()
        _NEXT_JOB_SEQUENCE += 1
        job = ResearchJob(
            id=str(uuid4()),
            query=query,
            preset=preset,
            created_order=_NEXT_JOB_SEQUENCE,
            created_at=created_at,
        )
        _JOBS[job.id] = job
        _prune_finished_jobs_locked()
        try:
            _persist_research_jobs_or_500_locked()
        except HTTPException:
            _restore_research_jobs_state_locked(snapshot)
            raise
        return _job_create_response(job)


def list_research_jobs(
    status: ResearchJobStatus | None,
    limit: int,
) -> dict[str, Any]:
    with _JOBS_LOCK:
        return _jobs_list_response_locked(status=status, limit=limit)


def summarize_research_jobs() -> dict[str, Any]:
    with _JOBS_LOCK:
        return _jobs_summary_response_locked()


def cancel_research_job(job_id: str, finished_at: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        if job.status != RESEARCH_JOB_STATUS_QUEUED:
            raise HTTPException(
                status_code=409,
                detail="Only queued research jobs can be cancelled.",
            )
        snapshot = _research_jobs_state_snapshot_locked()
        previous_status = job.status
        previous_finished_at = job.finished_at
        job.status = RESEARCH_JOB_STATUS_CANCELLED
        job.finished_at = finished_at
        _prune_finished_jobs_locked()
        try:
            _persist_research_jobs_or_500_locked()
        except HTTPException:
            job.status = previous_status
            job.finished_at = previous_finished_at
            _restore_research_jobs_state_locked(snapshot)
            raise
        return _job_detail(job, _queued_job_positions_locked())


def get_research_job(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        return _job_detail(job, _queued_job_positions_locked())
```

Add worker wrappers with timestamp creation still controlled by `api.py`:

```python
def mark_research_job_running(
    job_id: str,
    started_at: str,
    store_failure_finished_at,
) -> ResearchJob | None:
    with _JOBS_LOCK:
        job = _JOBS[job_id]
        if job.status == RESEARCH_JOB_STATUS_CANCELLED:
            return None
        job.status = RESEARCH_JOB_STATUS_RUNNING
        job.started_at = started_at
        try:
            _persist_research_jobs_locked()
        except ResearchJobsStoreError:
            job.status = RESEARCH_JOB_STATUS_FAILED
            job.finished_at = store_failure_finished_at()
            job.error = "Research job store failed."
            _prune_finished_jobs_locked()
            _persist_research_jobs_best_effort_locked()
            return None
        return job


def mark_research_job_failed(
    job: ResearchJob,
    finished_at: str,
    error: str,
) -> None:
    with _JOBS_LOCK:
        job.status = RESEARCH_JOB_STATUS_FAILED
        job.finished_at = finished_at
        job.error = error
        _prune_finished_jobs_locked()
        _persist_research_jobs_best_effort_locked()


def mark_research_job_succeeded(
    job: ResearchJob,
    finished_at: str,
    result: dict[str, Any],
) -> None:
    with _JOBS_LOCK:
        job.status = RESEARCH_JOB_STATUS_SUCCEEDED
        job.finished_at = finished_at
        job.result = result
        _prune_finished_jobs_locked()
        _persist_research_jobs_best_effort_locked()
```

`store_failure_finished_at` is a callable supplied by `api.py` so the second timestamp is only consumed if the running-transition store write fails.

- [ ] **Step 3: Run repository tests and verify green**

Run:

```bash
python -m pytest tests/test_research_jobs.py -q
```

Expected: repository tests pass after the new module exists.

## Task 3: Thin `api.py` To Use Repository Functions

**Files:**
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Replace API imports**

Remove from `api.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from uuid import uuid4
from insight_graph.research_jobs_store import (
    ResearchJobsStoreError,
    load_research_jobs,
    research_jobs_path_from_env,
    save_research_jobs,
)
```

Add:

```python
from threading import Lock

from insight_graph.research_jobs import (
    RESEARCH_JOB_STATUSES,
    ResearchJobStatus,
    cancel_research_job as cancel_research_job_record,
    create_research_job as create_research_job_record,
    get_research_job as get_research_job_record,
    initialize_research_jobs,
    list_research_jobs as list_research_job_records,
    mark_research_job_failed,
    mark_research_job_running,
    mark_research_job_succeeded,
    summarize_research_jobs,
)
```

- [ ] **Step 2: Remove moved state and helper code from `api.py`**

Delete these definitions from `api.py`:

```python
_JOBS_LOCK
_MAX_RESEARCH_JOBS
_MAX_ACTIVE_RESEARCH_JOBS
_RESEARCH_JOB_STATUS_QUEUED
_RESEARCH_JOB_STATUS_RUNNING
_RESEARCH_JOB_STATUS_SUCCEEDED
_RESEARCH_JOB_STATUS_FAILED
_RESEARCH_JOB_STATUS_CANCELLED
_RESEARCH_JOB_STATUSES
_ACTIVE_RESEARCH_JOB_STATUSES
_TERMINAL_RESEARCH_JOB_STATUSES
_NEXT_JOB_SEQUENCE
_JOBS
_RESEARCH_JOBS_PATH
ResearchJob
_research_job_from_store
initialize_research_jobs
ResearchJobsStateSnapshot
_research_jobs_state_snapshot_locked
_restore_research_jobs_state_locked
_persist_research_jobs_locked
_persist_research_jobs_or_500_locked
_job_timing_fields
_queued_job_positions_locked
_active_research_job_count_locked
_job_queue_position_field
_job_summary
_job_create_response
_job_detail
_jobs_list_response_locked
_jobs_summary_response_locked
_persist_research_jobs_best_effort_locked
_mark_research_job_running_locked
_mark_research_job_failed_locked
_mark_research_job_succeeded_locked
_prune_finished_jobs_locked
```

Keep `_RESEARCH_ENV_LOCK`, `_JOB_EXECUTOR`, `_current_utc_timestamp`, OpenAPI metadata constants, request/response models, routes, `_run_research_job`, and `app = create_app()`.

- [ ] **Step 3: Update query type alias in `api.py`**

Replace the current `ResearchJobStatusQuery` alias with:

```python
ResearchJobStatusQuery = Annotated[
    ResearchJobStatus | None,
    Query(description="Filter jobs by status. Omit to return all retained jobs."),
]
```

- [ ] **Step 4: Update repository initialization call in `api.py`**

Replace:

```python
initialize_research_jobs()
```

with:

```python
initialize_research_jobs(restart_timestamp=_current_utc_timestamp())
```

- [ ] **Step 5: Update research job routes in `api.py`**

Use repository functions in route bodies:

```python
def create_research_job(request: ResearchRequest) -> dict[str, str]:
    response = create_research_job_record(
        query=request.query,
        preset=request.preset,
        created_at=_current_utc_timestamp(),
    )
    _JOB_EXECUTOR.submit(_run_research_job, response["job_id"])
    return response
```

```python
def list_research_jobs(
    status: ResearchJobStatusQuery = None,
    limit: ResearchJobsLimitQuery = 100,
) -> dict[str, Any]:
    return list_research_job_records(status=status, limit=limit)
```

```python
def summarize_research_jobs() -> dict[str, Any]:
    return summarize_research_jobs()
```

Avoid the name collision above by importing the repository function as `summarize_research_jobs_state` if needed:

```python
summarize_research_jobs as summarize_research_jobs_state,
```

Then route body should be:

```python
return summarize_research_jobs_state()
```

```python
def cancel_research_job(job_id: str) -> dict[str, Any]:
    return cancel_research_job_record(
        job_id=job_id,
        finished_at=_current_utc_timestamp(),
    )
```

```python
def get_research_job(job_id: str) -> dict[str, Any]:
    return get_research_job_record(job_id)
```

- [ ] **Step 6: Update worker orchestration in `api.py`**

Replace `_run_research_job` with:

```python
def _run_research_job(job_id: str) -> None:
    job = mark_research_job_running(
        job_id=job_id,
        started_at=_current_utc_timestamp(),
        store_failure_finished_at=_current_utc_timestamp,
    )
    if job is None:
        return

    try:
        with _RESEARCH_ENV_LOCK:
            with _research_preset_environment(job.preset):
                state = run_research(job.query)
        result = _build_research_json_payload(state)
    except Exception:
        mark_research_job_failed(
            job,
            finished_at=_current_utc_timestamp(),
            error="Research workflow failed.",
        )
        return

    mark_research_job_succeeded(
        job,
        finished_at=_current_utc_timestamp(),
        result=result,
    )
```

- [ ] **Step 7: Run API import smoke test**

Run:

```bash
python -c "import insight_graph.api as api; print(api.app.title)"
```

Expected: prints `InsightGraph API`.

## Task 4: Migrate API Tests Away From Old `api.py` Internals

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add repository module import**

Add after the existing `import insight_graph.api as api_module`:

```python
import insight_graph.research_jobs as jobs_module
```

- [ ] **Step 2: Update API tests that need repository state**

Use these replacements in `tests/test_api.py`:

```python
api_module.ResearchJob -> jobs_module.ResearchJob
api_module._JOBS -> jobs_module._JOBS
api_module._JOBS_LOCK -> jobs_module._JOBS_LOCK
api_module._NEXT_JOB_SEQUENCE -> jobs_module._NEXT_JOB_SEQUENCE
api_module._RESEARCH_JOBS_PATH -> jobs_module._RESEARCH_JOBS_PATH
api_module._MAX_RESEARCH_JOBS -> jobs_module._MAX_RESEARCH_JOBS
api_module._MAX_ACTIVE_RESEARCH_JOBS -> jobs_module._MAX_ACTIVE_RESEARCH_JOBS
api_module._persist_research_jobs_locked -> jobs_module._persist_research_jobs_locked
api_module.ResearchJobsStoreError -> jobs_module.ResearchJobsStoreError
api_module.initialize_research_jobs( -> jobs_module.initialize_research_jobs(restart_timestamp=
api_module._research_jobs_state_snapshot_locked -> jobs_module._research_jobs_state_snapshot_locked
api_module._restore_research_jobs_state_locked -> jobs_module._restore_research_jobs_state_locked
```

For `initialize_research_jobs()` calls in API tests, pass an explicit timestamp:

```python
jobs_module.initialize_research_jobs(restart_timestamp="2026-04-27T21:00:00Z")
```

For tests that monkeypatch `api_module._current_utc_timestamp` before initialization, stop monkeypatching time and pass the expected timestamp to `jobs_module.initialize_research_jobs(...)`.

- [ ] **Step 3: Remove repository-only tests from `tests/test_api.py` after they exist in `tests/test_research_jobs.py`**

Delete these tests from `tests/test_api.py` because Task 1 moved them to `tests/test_research_jobs.py`:

```python
test_research_job_status_constants_match_public_statuses
test_job_create_response_builder_returns_public_shape
test_initialize_research_jobs_noops_without_store_path
test_initialize_research_jobs_loads_configured_store
test_initialize_research_jobs_fails_closed_for_bad_store
test_research_jobs_state_snapshot_restores_jobs_and_sequence
test_load_research_jobs_from_store_restores_jobs
test_load_research_jobs_from_store_marks_unfinished_jobs_failed
```

- [ ] **Step 4: Run API tests and fix import/reference fallout**

Run:

```bash
python -m pytest tests/test_api.py -q
```

Expected: all API tests pass. If failures are missing old private names on `api_module`, update the test to use `jobs_module`; do not add compatibility aliases to `api.py`.

## Task 5: Verify Repository Split And Commit

**Files:**
- Create: `src/insight_graph/research_jobs.py`
- Create: `tests/test_research_jobs.py`
- Modify: `src/insight_graph/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Run focused repository tests**

Run:

```bash
python -m pytest tests/test_research_jobs.py -q
```

Expected: all repository tests pass.

- [ ] **Step 2: Run focused API tests**

Run:

```bash
python -m pytest tests/test_api.py -q
```

Expected: all API tests pass.

- [ ] **Step 3: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass with the existing skipped test count unchanged.

- [ ] **Step 4: Run linter**

Run:

```bash
python -m ruff check .
```

Expected: `All checks passed!`.

- [ ] **Step 5: Review diff boundaries**

Run:

```bash
git diff -- src/insight_graph/api.py src/insight_graph/research_jobs.py tests/test_api.py tests/test_research_jobs.py
```

Expected: diff shows repository code moved out of `api.py`, API routes calling repository functions, and tests using `jobs_module` for repository state. It should not show endpoint path changes, response shape changes, OpenAPI metadata rewrites unrelated to imports, persistence schema changes, or worker concurrency changes.

- [ ] **Step 6: Commit implementation**

Run:

```bash
git add src/insight_graph/api.py src/insight_graph/research_jobs.py tests/test_api.py tests/test_research_jobs.py
git commit -m "refactor: split research job repository"
```

Expected: commit succeeds.

## Self-Review

- Spec coverage: one repository module, no old private aliases in `api.py`, deterministic timestamp passing, route behavior preserved, and repository tests added.
- Placeholder scan: no placeholder steps remain.
- Type consistency: repository `ResearchJobStatus` is a plain `Literal`; API wraps it with `Annotated[..., Query(...)]` for OpenAPI.
- Runtime behavior stays unchanged: same endpoints, response bodies, statuses, store schema, active limits, retention limits, and worker semantics.
