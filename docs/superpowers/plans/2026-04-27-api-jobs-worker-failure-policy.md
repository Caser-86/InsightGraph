# API Jobs Worker Failure Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `_run_research_job` state transitions explicit and keep worker futures from failing on terminal JSON persistence errors.

**Architecture:** Keep the current in-process worker in `src/insight_graph/api.py`. Add small locked helper functions for running, failed, and succeeded transitions; each helper owns timestamps, pruning, and persistence behavior for that transition.

**Tech Stack:** Python 3.11+, FastAPI, pytest, ruff, in-process `ThreadPoolExecutor`, dataclasses.

---

## File Structure

- Modify `src/insight_graph/api.py`: add locked job transition helpers and simplify `_run_research_job` to call them.
- Modify `tests/test_api.py`: add worker failure-policy tests beside the existing research job persistence tests.

## Task 1: Add Worker Failure-Policy Tests

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add failing tests after `test_run_research_job_marks_failed_when_running_store_write_fails`**

Insert this code after the existing running store write failure test:

```python
def test_run_research_job_keeps_failed_state_when_terminal_store_write_fails(
    monkeypatch,
    tmp_path,
) -> None:
    persist_calls = 0

    def fail_second_persist() -> None:
        nonlocal persist_calls
        persist_calls += 1
        if persist_calls == 2:
            raise api_module.ResearchJobsStoreError("secret path")

    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider payload")

    store_path = tmp_path / "jobs.json"
    job = api_module.ResearchJob(
        id="job-terminal-failure",
        query="Fail terminal persist",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", store_path)
    monkeypatch.setattr(api_module, "_persist_research_jobs_locked", fail_second_persist)
    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence("2026-04-27T20:00:01Z", "2026-04-27T20:00:02Z"),
    )
    api_module._JOBS.clear()
    api_module._JOBS[job.id] = job

    api_module._run_research_job(job.id)

    assert persist_calls == 2
    assert job.status == "failed"
    assert job.started_at == "2026-04-27T20:00:01Z"
    assert job.finished_at == "2026-04-27T20:00:02Z"
    assert job.error == "Research workflow failed."


def test_run_research_job_keeps_success_state_when_terminal_store_write_fails(
    monkeypatch,
    tmp_path,
) -> None:
    persist_calls = 0

    def fail_second_persist() -> None:
        nonlocal persist_calls
        persist_calls += 1
        if persist_calls == 2:
            raise api_module.ResearchJobsStoreError("secret path")

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    store_path = tmp_path / "jobs.json"
    job = api_module.ResearchJob(
        id="job-terminal-success",
        query="Succeed terminal persist",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", store_path)
    monkeypatch.setattr(api_module, "_persist_research_jobs_locked", fail_second_persist)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence("2026-04-27T20:00:01Z", "2026-04-27T20:00:02Z"),
    )
    api_module._JOBS.clear()
    api_module._JOBS[job.id] = job

    api_module._run_research_job(job.id)

    assert persist_calls == 2
    assert job.status == "succeeded"
    assert job.started_at == "2026-04-27T20:00:01Z"
    assert job.finished_at == "2026-04-27T20:00:02Z"
    assert job.result is not None
    assert job.result["user_request"] == "Succeed terminal persist"


def test_run_research_job_skips_cancelled_job_without_store_write(
    monkeypatch,
    tmp_path,
) -> None:
    def fail_persist() -> None:
        raise AssertionError("persist should not be called")

    def fail_if_called(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    store_path = tmp_path / "jobs.json"
    job = api_module.ResearchJob(
        id="job-cancelled-before-worker",
        query="Cancelled",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
        status="cancelled",
        finished_at="2026-04-27T20:00:01Z",
    )
    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", store_path)
    monkeypatch.setattr(api_module, "_persist_research_jobs_locked", fail_persist)
    monkeypatch.setattr(api_module, "run_research", fail_if_called)
    api_module._JOBS.clear()
    api_module._JOBS[job.id] = job

    api_module._run_research_job(job.id)

    assert job.status == "cancelled"
    assert job.started_at is None
    assert job.finished_at == "2026-04-27T20:00:01Z"
```

- [ ] **Step 2: Run new tests and verify red**

Run:

```bash
python -m pytest tests/test_api.py::test_run_research_job_keeps_failed_state_when_terminal_store_write_fails tests/test_api.py::test_run_research_job_keeps_success_state_when_terminal_store_write_fails tests/test_api.py::test_run_research_job_skips_cancelled_job_without_store_write -q
```

Expected: first two tests fail because terminal `_persist_research_jobs_locked()` errors escape `_run_research_job`; cancelled test may pass.

## Task 2: Add Locked Worker Transition Helpers

**Files:**
- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Add helper functions before `_run_research_job`**

Insert this code immediately before `_run_research_job`:

```python
def _persist_research_jobs_best_effort_locked() -> None:
    try:
        _persist_research_jobs_locked()
    except ResearchJobsStoreError:
        pass


def _mark_research_job_running_locked(job: ResearchJob) -> bool:
    if job.status == _RESEARCH_JOB_STATUS_CANCELLED:
        return False
    job.status = _RESEARCH_JOB_STATUS_RUNNING
    job.started_at = _current_utc_timestamp()
    try:
        _persist_research_jobs_locked()
    except ResearchJobsStoreError:
        job.status = _RESEARCH_JOB_STATUS_FAILED
        job.finished_at = _current_utc_timestamp()
        job.error = "Research job store failed."
        _prune_finished_jobs_locked()
        _persist_research_jobs_best_effort_locked()
        return False
    return True


def _mark_research_job_failed_locked(job: ResearchJob, error: str) -> None:
    job.status = _RESEARCH_JOB_STATUS_FAILED
    job.finished_at = _current_utc_timestamp()
    job.error = error
    _prune_finished_jobs_locked()
    _persist_research_jobs_best_effort_locked()


def _mark_research_job_succeeded_locked(
    job: ResearchJob,
    result: dict[str, Any],
) -> None:
    job.status = _RESEARCH_JOB_STATUS_SUCCEEDED
    job.finished_at = _current_utc_timestamp()
    job.result = result
    _prune_finished_jobs_locked()
    _persist_research_jobs_best_effort_locked()
```

- [ ] **Step 2: Replace `_run_research_job` with helper calls**

Replace the full `_run_research_job` function with:

```python
def _run_research_job(job_id: str) -> None:
    with _JOBS_LOCK:
        job = _JOBS[job_id]
        if not _mark_research_job_running_locked(job):
            return

    try:
        with _RESEARCH_ENV_LOCK:
            with _research_preset_environment(job.preset):
                state = run_research(job.query)
        result = _build_research_json_payload(state)
    except Exception:
        with _JOBS_LOCK:
            _mark_research_job_failed_locked(
                job,
                "Research workflow failed.",
            )
        return

    with _JOBS_LOCK:
        _mark_research_job_succeeded_locked(job, result)
```

- [ ] **Step 3: Run worker failure-policy tests and verify green**

Run:

```bash
python -m pytest tests/test_api.py::test_run_research_job_marks_failed_when_running_store_write_fails tests/test_api.py::test_run_research_job_keeps_failed_state_when_terminal_store_write_fails tests/test_api.py::test_run_research_job_keeps_success_state_when_terminal_store_write_fails tests/test_api.py::test_run_research_job_skips_cancelled_job_without_store_write -q
```

Expected: `4 passed`.

## Task 3: Run Focused Regression Tests

**Files:**
- Test: `tests/test_api.py`

- [ ] **Step 1: Run API job tests around persistence and lifecycle**

Run:

```bash
python -m pytest tests/test_api.py -q
```

Expected: all `tests/test_api.py` tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass with the existing skipped test count unchanged.

- [ ] **Step 3: Run linter**

Run:

```bash
python -m ruff check .
```

Expected: `All checks passed!`.

## Task 4: Commit Implementation

**Files:**
- Modify: `src/insight_graph/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Review diff**

Run:

```bash
git diff -- src/insight_graph/api.py tests/test_api.py
```

Expected: diff only contains worker transition helpers, `_run_research_job` simplification, and new tests.

- [ ] **Step 2: Commit implementation**

Run:

```bash
git add src/insight_graph/api.py tests/test_api.py
git commit -m "fix: contain research job worker store failures"
```

Expected: commit succeeds.

## Self-Review

- Spec coverage: cancelled-before-start, running-store failure, workflow failure, workflow success, and terminal store failure are covered by tests and helper transitions.
- Placeholder scan: no placeholder steps or deferred implementation notes remain.
- Type consistency: helper signatures use existing `ResearchJob`, `dict[str, Any]`, and existing job status constants.
- Public API shape stays unchanged.
- Store schema stays unchanged.
