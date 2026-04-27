# API Jobs Lifecycle And Repository Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate FastAPI app creation and research job state operations from endpoint handlers while preserving all public API and JSON persistence behavior.

**Architecture:** Keep `src/insight_graph/api.py` as the public API module, but introduce explicit lifecycle helpers and a small in-process job state helper boundary. Preserve the module-level `app = create_app()` compatibility path and keep `research_jobs_store.py` as the JSON serialization layer.

**Tech Stack:** Python 3.11+, FastAPI, dataclasses, threading lock, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/api.py`: add `create_app()`, explicit job initialization helper, and small state snapshot/restore helpers to reduce endpoint rollback duplication.
- Modify `tests/test_api.py`: add lifecycle tests and update persistence tests to use explicit initialization where possible.
- Modify `docs/architecture.md`: clarify that API jobs have an explicit initialization boundary for the current MVP.

## Task 1: Add App Factory Tests

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add failing tests near health/API setup tests**

Insert after `test_health_returns_ok`:

```python
def test_create_app_returns_configured_fastapi_app() -> None:
    app = api_module.create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_module_level_app_remains_configured() -> None:
    route_paths = {route.path for route in api_module.app.routes}

    assert "/health" in route_paths
    assert "/research/jobs" in route_paths
    assert "/research/jobs/{job_id}" in route_paths
```

- [ ] **Step 2: Run tests and verify red**

Run:

```bash
python -m pytest tests/test_api.py::test_create_app_returns_configured_fastapi_app tests/test_api.py::test_module_level_app_remains_configured -q
```

Expected: first test fails because `create_app` is not defined; second may pass.

- [ ] **Step 3: Implement app factory in `src/insight_graph/api.py`**

Replace the top-level app assignment:

```python
app = FastAPI(title="InsightGraph API")
```

with:

```python
def create_app() -> FastAPI:
    return FastAPI(title="InsightGraph API")


app = create_app()
```

Keep all existing route decorators using the module-level `app`.

- [ ] **Step 4: Run app factory tests**

Run:

```bash
python -m pytest tests/test_api.py::test_create_app_returns_configured_fastapi_app tests/test_api.py::test_module_level_app_remains_configured -q
```

Expected: `2 passed`.

## Task 2: Add Explicit Job Initialization Tests

**Files:**
- Modify: `tests/test_api.py`
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Add failing initialization tests near persistence tests**

Insert before `test_create_research_job_writes_configured_store`:

```python
def test_initialize_research_jobs_noops_without_store_path(monkeypatch) -> None:
    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", None)
    api_module._NEXT_JOB_SEQUENCE = 8
    api_module._JOBS.clear()
    api_module._JOBS["existing"] = api_module.ResearchJob(
        id="existing",
        query="Existing",
        preset=api_module.ResearchPreset.offline,
        created_order=8,
        created_at="2026-04-27T20:00:00Z",
    )

    api_module.initialize_research_jobs()

    assert api_module._NEXT_JOB_SEQUENCE == 8
    assert set(api_module._JOBS) == {"existing"}


def test_initialize_research_jobs_loads_configured_store(monkeypatch, tmp_path) -> None:
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
    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", store_path)
    api_module._JOBS.clear()
    api_module._NEXT_JOB_SEQUENCE = 0

    api_module.initialize_research_jobs()

    assert api_module._NEXT_JOB_SEQUENCE == 4
    assert api_module._JOBS["job-4"].status == "succeeded"
```

- [ ] **Step 2: Run initialization tests and verify red**

Run:

```bash
python -m pytest tests/test_api.py::test_initialize_research_jobs_noops_without_store_path tests/test_api.py::test_initialize_research_jobs_loads_configured_store -q
```

Expected: FAIL because `initialize_research_jobs` is not defined.

- [ ] **Step 3: Rename private loader to explicit initializer**

In `src/insight_graph/api.py`, rename:

```python
def _load_research_jobs_from_store() -> None:
```

to:

```python
def initialize_research_jobs() -> None:
```

Update the bottom call from:

```python
_load_research_jobs_from_store()
```

to:

```python
initialize_research_jobs()
```

Update existing tests that call `_load_research_jobs_from_store()` to call `initialize_research_jobs()`.

- [ ] **Step 4: Run initialization and existing load tests**

Run:

```bash
python -m pytest tests/test_api.py::test_initialize_research_jobs_noops_without_store_path tests/test_api.py::test_initialize_research_jobs_loads_configured_store tests/test_api.py::test_load_research_jobs_from_store_restores_jobs tests/test_api.py::test_load_research_jobs_from_store_marks_unfinished_jobs_failed -q
```

Expected: all listed tests pass.

## Task 3: Add Job State Snapshot Helpers For Rollback

**Files:**
- Modify: `src/insight_graph/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add helper-focused tests near persistence rollback tests**

Insert before `test_create_research_job_returns_safe_500_when_store_write_fails`:

```python
def test_research_jobs_state_snapshot_restores_jobs_and_sequence() -> None:
    original = api_module.ResearchJob(
        id="job-1",
        query="Original",
        preset=api_module.ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    api_module._NEXT_JOB_SEQUENCE = 1
    api_module._JOBS.clear()
    api_module._JOBS[original.id] = original
    snapshot = api_module._research_jobs_state_snapshot_locked()

    api_module._NEXT_JOB_SEQUENCE = 2
    api_module._JOBS.clear()

    api_module._restore_research_jobs_state_locked(snapshot)

    assert api_module._NEXT_JOB_SEQUENCE == 1
    assert api_module._JOBS == {"job-1": original}
```

- [ ] **Step 2: Run snapshot test and verify red**

Run:

```bash
python -m pytest tests/test_api.py::test_research_jobs_state_snapshot_restores_jobs_and_sequence -q
```

Expected: FAIL because snapshot helpers are not defined.

- [ ] **Step 3: Add state snapshot helpers**

In `src/insight_graph/api.py`, add after `initialize_research_jobs()`:

```python
@dataclass(frozen=True)
class ResearchJobsStateSnapshot:
    next_job_sequence: int
    jobs: dict[str, ResearchJob]


def _research_jobs_state_snapshot_locked() -> ResearchJobsStateSnapshot:
    return ResearchJobsStateSnapshot(
        next_job_sequence=_NEXT_JOB_SEQUENCE,
        jobs=dict(_JOBS),
    )


def _restore_research_jobs_state_locked(snapshot: ResearchJobsStateSnapshot) -> None:
    global _NEXT_JOB_SEQUENCE

    _NEXT_JOB_SEQUENCE = snapshot.next_job_sequence
    _JOBS.clear()
    _JOBS.update(snapshot.jobs)
```

- [ ] **Step 4: Use snapshot helpers in rollback paths**

Replace create rollback locals:

```python
previous_sequence = _NEXT_JOB_SEQUENCE
previous_jobs = dict(_JOBS)
```

with:

```python
snapshot = _research_jobs_state_snapshot_locked()
```

and replace rollback body:

```python
_JOBS.clear()
_JOBS.update(previous_jobs)
_NEXT_JOB_SEQUENCE = previous_sequence
```

with:

```python
_restore_research_jobs_state_locked(snapshot)
```

Replace cancel rollback local `previous_jobs = dict(_JOBS)` with `snapshot = _research_jobs_state_snapshot_locked()` and replace `_JOBS.clear(); _JOBS.update(previous_jobs)` with `_restore_research_jobs_state_locked(snapshot)`. Keep the explicit `job.status` and `job.finished_at` reset before restoring, so existing object references in tests remain correct.

- [ ] **Step 5: Run rollback tests**

Run:

```bash
python -m pytest tests/test_api.py::test_research_jobs_state_snapshot_restores_jobs_and_sequence tests/test_api.py::test_create_research_job_returns_safe_500_when_store_write_fails tests/test_api.py::test_create_research_job_restores_pruned_jobs_when_store_write_fails tests/test_api.py::test_cancel_research_job_rolls_back_when_store_write_fails tests/test_api.py::test_cancel_research_job_restores_pruned_jobs_when_store_write_fails -q
```

Expected: all listed tests pass.

## Task 4: Reduce Import-Time Store Coupling In Tests

**Files:**
- Modify: `tests/test_api.py`
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Ensure import-time initialization remains one explicit call**

Verify `src/insight_graph/api.py` has exactly one module-level call:

```python
initialize_research_jobs()
```

No code edit is needed if this is already true.

- [ ] **Step 2: Add bad JSON explicit initializer test**

Insert near initialization tests:

```python
def test_initialize_research_jobs_fails_closed_for_bad_store(monkeypatch, tmp_path) -> None:
    store_path = tmp_path / "jobs.json"
    store_path.write_text("{bad-json", encoding="utf-8")
    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", store_path)

    with pytest.raises(api_module.ResearchJobsStoreError):
        api_module.initialize_research_jobs()
```

Add `import pytest` to `tests/test_api.py` if not already present.

- [ ] **Step 3: Run initialization tests**

Run:

```bash
python -m pytest tests/test_api.py::test_initialize_research_jobs_noops_without_store_path tests/test_api.py::test_initialize_research_jobs_loads_configured_store tests/test_api.py::test_initialize_research_jobs_fails_closed_for_bad_store -q
```

Expected: `3 passed`.

## Task 5: Documentation And Verification

**Files:**
- Modify: `docs/architecture.md`

- [ ] **Step 1: Update architecture wording**

In the API jobs `任务追踪` paragraph, add that the current MVP now has an explicit API jobs initialization boundary but still uses single-process memory plus optional JSON metadata persistence.

- [ ] **Step 2: Run focused API/store tests**

Run:

```bash
python -m pytest tests/test_api.py tests/test_research_jobs_store.py -q
```

Expected: all API and store tests pass.

- [ ] **Step 3: Run full verification**

Run:

```bash
python -m pytest -q
python -m ruff check .
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 4: Review diff and commit**

Run:

```bash
git diff -- src/insight_graph/api.py tests/test_api.py docs/architecture.md
git add src/insight_graph/api.py tests/test_api.py docs/architecture.md
git commit -m "refactor: clarify research job lifecycle"
```

Expected: commit includes lifecycle/refactor changes only; no public API behavior changes.

## Self-Review

- Spec coverage: app factory, module-level compatibility, explicit job initialization, no-op without store path, bad JSON fail closed, rollback helper boundary, and docs are covered.
- Placeholder scan: no placeholders or vague steps remain.
- Type consistency: `initialize_research_jobs()`, `ResearchJobsStateSnapshot`, `_research_jobs_state_snapshot_locked()`, and `_restore_research_jobs_state_locked()` are named consistently.
- Scope check: no worker policy changes, retry changes, endpoint response changes, persistence backend changes, or OpenAPI polish are included.
