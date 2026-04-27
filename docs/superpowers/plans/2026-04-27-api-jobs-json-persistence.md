# API Jobs JSON Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in JSON persistence for research job metadata without changing public API response shapes.

**Architecture:** Add a small standard-library storage module for JSON serialization, deserialization, restart recovery, and atomic writes. Keep endpoint logic and locking in `api.py`; integrate persistence through narrow helper functions that are no-ops unless `INSIGHT_GRAPH_RESEARCH_JOBS_PATH` is set.

**Tech Stack:** Python 3.11+, FastAPI, dataclasses, standard-library `json`, `os.replace`, `tempfile`, pytest, ruff.

---

## File Structure

- Create `src/insight_graph/research_jobs_store.py`: JSON store helpers, constants, validation, restart recovery, atomic save.
- Create `tests/test_research_jobs_store.py`: unit tests for pure store behavior.
- Modify `src/insight_graph/api.py`: configure optional store path, load persisted jobs, persist state mutations, expose safe HTTP 500 on request-time store failures.
- Modify `tests/test_api.py`: API integration tests for opt-in writes, reload, restart recovery, write failure, and unchanged default behavior.
- Modify `docs/configuration.md`: document `INSIGHT_GRAPH_RESEARCH_JOBS_PATH`.
- Modify `docs/architecture.md`: update API jobs persistence status.

## Task 1: Store Module Serialization

**Files:**
- Create: `tests/test_research_jobs_store.py`
- Create: `src/insight_graph/research_jobs_store.py`

- [ ] **Step 1: Write failing serialization tests**

Create `tests/test_research_jobs_store.py` with:

```python
from dataclasses import dataclass

from insight_graph.research_jobs_store import serialize_research_job


@dataclass
class FakeJob:
    id: str
    query: str
    preset: object
    created_order: int
    created_at: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, object] | None = None
    error: str | None = None


class FakePreset:
    value = "offline"


def test_serialize_research_job_uses_public_fields() -> None:
    job = FakeJob(
        id="job-1",
        query="Compare Cursor",
        preset=FakePreset(),
        created_order=7,
        created_at="2026-04-27T10:00:00Z",
        status="succeeded",
        started_at="2026-04-27T10:00:01Z",
        finished_at="2026-04-27T10:00:02Z",
        result={"report_markdown": "# Report"},
    )

    assert serialize_research_job(job) == {
        "id": "job-1",
        "query": "Compare Cursor",
        "preset": "offline",
        "created_order": 7,
        "created_at": "2026-04-27T10:00:00Z",
        "status": "succeeded",
        "started_at": "2026-04-27T10:00:01Z",
        "finished_at": "2026-04-27T10:00:02Z",
        "result": {"report_markdown": "# Report"},
        "error": None,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_research_jobs_store.py::test_serialize_research_job_uses_public_fields -q
```

Expected: FAIL because `insight_graph.research_jobs_store` does not exist.

- [ ] **Step 3: Implement minimal store module**

Create `src/insight_graph/research_jobs_store.py` with:

```python
from typing import Any

RESEARCH_JOBS_PATH_ENV = "INSIGHT_GRAPH_RESEARCH_JOBS_PATH"
RESTART_FAILURE_ERROR = "Research job did not complete before server restart."


class ResearchJobsStoreError(RuntimeError):
    pass


def serialize_research_job(job: Any) -> dict[str, Any]:
    preset = job.preset.value if hasattr(job.preset, "value") else job.preset
    return {
        "id": job.id,
        "query": job.query,
        "preset": preset,
        "created_order": job.created_order,
        "created_at": job.created_at,
        "status": job.status,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result": job.result,
        "error": job.error,
    }
```

- [ ] **Step 4: Run serialization test**

Run:

```bash
python -m pytest tests/test_research_jobs_store.py::test_serialize_research_job_uses_public_fields -q
```

Expected: `1 passed`.

## Task 2: JSON Load, Save, And Restart Recovery

**Files:**
- Modify: `tests/test_research_jobs_store.py`
- Modify: `src/insight_graph/research_jobs_store.py`

- [ ] **Step 1: Add failing store tests**

Append to `tests/test_research_jobs_store.py`:

```python
import json

import pytest

from insight_graph.research_jobs_store import (
    RESTART_FAILURE_ERROR,
    ResearchJobsStoreError,
    load_research_jobs,
    research_jobs_path_from_env,
    save_research_jobs,
)


def test_research_jobs_path_from_env_returns_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_PATH", raising=False)

    assert research_jobs_path_from_env() is None


def test_save_and_load_research_jobs_round_trips_terminal_jobs(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    job = FakeJob(
        id="job-1",
        query="Compare Cursor",
        preset="offline",
        created_order=3,
        created_at="2026-04-27T10:00:00Z",
        status="succeeded",
        started_at="2026-04-27T10:00:01Z",
        finished_at="2026-04-27T10:00:02Z",
        result={"report_markdown": "# Report"},
    )

    save_research_jobs(path=path, jobs=[job], next_job_sequence=3)
    loaded = load_research_jobs(
        path=path,
        restart_timestamp="2026-04-27T11:00:00Z",
    )

    assert loaded.next_job_sequence == 3
    assert loaded.jobs == [serialize_research_job(job)]
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["next_job_sequence"] == 3
    assert raw["jobs"][0]["id"] == "job-1"


def test_load_research_jobs_marks_unfinished_jobs_failed(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text(
        json.dumps(
            {
                "next_job_sequence": 2,
                "jobs": [
                    {
                        "id": "queued-job",
                        "query": "Queued",
                        "preset": "offline",
                        "created_order": 1,
                        "created_at": "2026-04-27T10:00:00Z",
                        "status": "queued",
                        "started_at": None,
                        "finished_at": None,
                        "result": None,
                        "error": None,
                    },
                    {
                        "id": "running-job",
                        "query": "Running",
                        "preset": "offline",
                        "created_order": 2,
                        "created_at": "2026-04-27T10:00:01Z",
                        "status": "running",
                        "started_at": "2026-04-27T10:00:02Z",
                        "finished_at": None,
                        "result": None,
                        "error": None,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_research_jobs(
        path=path,
        restart_timestamp="2026-04-27T11:00:00Z",
    )

    assert [job["status"] for job in loaded.jobs] == ["failed", "failed"]
    assert [job["finished_at"] for job in loaded.jobs] == [
        "2026-04-27T11:00:00Z",
        "2026-04-27T11:00:00Z",
    ]
    assert [job["error"] for job in loaded.jobs] == [
        RESTART_FAILURE_ERROR,
        RESTART_FAILURE_ERROR,
    ]


def test_load_research_jobs_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ResearchJobsStoreError):
        load_research_jobs(path=path, restart_timestamp="2026-04-27T11:00:00Z")
```

- [ ] **Step 2: Run new store tests to verify they fail**

Run:

```bash
python -m pytest tests/test_research_jobs_store.py -q
```

Expected: FAIL because load/save/path helpers and `LoadedResearchJobs` are missing.

- [ ] **Step 3: Implement JSON store helpers**

Replace `src/insight_graph/research_jobs_store.py` with:

```python
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RESEARCH_JOBS_PATH_ENV = "INSIGHT_GRAPH_RESEARCH_JOBS_PATH"
RESTART_FAILURE_ERROR = "Research job did not complete before server restart."
_REQUIRED_JOB_FIELDS = {
    "id",
    "query",
    "preset",
    "created_order",
    "created_at",
    "status",
    "started_at",
    "finished_at",
    "result",
    "error",
}


class ResearchJobsStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedResearchJobs:
    next_job_sequence: int
    jobs: list[dict[str, Any]]


def research_jobs_path_from_env() -> Path | None:
    value = os.environ.get(RESEARCH_JOBS_PATH_ENV)
    if value is None or not value.strip():
        return None
    return Path(value)


def serialize_research_job(job: Any) -> dict[str, Any]:
    preset = job.preset.value if hasattr(job.preset, "value") else job.preset
    return {
        "id": job.id,
        "query": job.query,
        "preset": preset,
        "created_order": job.created_order,
        "created_at": job.created_at,
        "status": job.status,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result": job.result,
        "error": job.error,
    }


def save_research_jobs(path: Path, jobs: list[Any], next_job_sequence: int) -> None:
    payload = {
        "jobs": [serialize_research_job(job) for job in jobs],
        "next_job_sequence": next_job_sequence,
    }
    try:
        _atomic_write_json(path, payload)
    except OSError as exc:
        raise ResearchJobsStoreError("Research jobs store write failed.") from exc


def load_research_jobs(path: Path, restart_timestamp: str) -> LoadedResearchJobs:
    if not path.exists():
        return LoadedResearchJobs(next_job_sequence=0, jobs=[])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchJobsStoreError("Research jobs store load failed.") from exc

    if not isinstance(payload, dict):
        raise ResearchJobsStoreError("Research jobs store payload must be an object.")
    next_job_sequence = payload.get("next_job_sequence")
    jobs = payload.get("jobs")
    if not isinstance(next_job_sequence, int) or not isinstance(jobs, list):
        raise ResearchJobsStoreError("Research jobs store schema is invalid.")

    loaded_jobs = [_load_job(item, restart_timestamp) for item in jobs]
    return LoadedResearchJobs(
        next_job_sequence=next_job_sequence,
        jobs=loaded_jobs,
    )


def _load_job(item: object, restart_timestamp: str) -> dict[str, Any]:
    if not isinstance(item, dict) or set(item) != _REQUIRED_JOB_FIELDS:
        raise ResearchJobsStoreError("Research jobs store job schema is invalid.")
    job = dict(item)
    if job["status"] in {"queued", "running"}:
        job["status"] = "failed"
        job["finished_at"] = restart_timestamp
        job["error"] = RESTART_FAILURE_ERROR
    return job


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, sort_keys=True)
            file.write("\n")
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise
```

- [ ] **Step 4: Run store tests**

Run:

```bash
python -m pytest tests/test_research_jobs_store.py -q
```

Expected: all store tests pass.

## Task 3: API Integration For Opt-In Persistence

**Files:**
- Modify: `tests/test_api.py`
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Add failing API persistence tests**

Append these tests near existing jobs API tests in `tests/test_api.py`:

```python
def test_create_research_job_writes_configured_store(monkeypatch, tmp_path) -> None:
    store_path = tmp_path / "jobs.json"
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", store_path)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "_current_utc_timestamp", lambda: "2026-04-27T20:00:00Z")
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    response = client.post("/research/jobs", json={"query": "Persist me"})

    assert response.status_code == 202
    payload = store_path.read_text(encoding="utf-8")
    assert '"next_job_sequence"' in payload
    assert '"query": "Persist me"' in payload


def test_load_research_jobs_from_store_restores_jobs(monkeypatch, tmp_path) -> None:
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

    api_module._load_research_jobs_from_store()

    assert api_module._NEXT_JOB_SEQUENCE == 4
    assert api_module._JOBS["job-4"].status == "succeeded"
    assert api_module._JOBS["job-4"].result == {"report_markdown": "# Report"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_api.py::test_create_research_job_writes_configured_store tests/test_api.py::test_load_research_jobs_from_store_restores_jobs -q
```

Expected: FAIL because `_RESEARCH_JOBS_PATH`, `_persist_research_jobs_locked`, and `_load_research_jobs_from_store` are missing.

- [ ] **Step 3: Integrate store in `src/insight_graph/api.py`**

Add imports:

```python
from pathlib import Path
```

and:

```python
from insight_graph.research_jobs_store import (
    ResearchJobsStoreError,
    load_research_jobs,
    research_jobs_path_from_env,
    save_research_jobs,
)
```

Add module global after `_JOBS`:

```python
_RESEARCH_JOBS_PATH: Path | None = research_jobs_path_from_env()
```

Add helpers after `_current_utc_timestamp()`:

```python
def _research_job_from_store(item: dict[str, Any]) -> ResearchJob:
    return ResearchJob(
        id=item["id"],
        query=item["query"],
        preset=ResearchPreset(item["preset"]),
        created_order=item["created_order"],
        created_at=item["created_at"],
        status=item["status"],
        started_at=item["started_at"],
        finished_at=item["finished_at"],
        result=item["result"],
        error=item["error"],
    )


def _load_research_jobs_from_store() -> None:
    global _NEXT_JOB_SEQUENCE

    if _RESEARCH_JOBS_PATH is None:
        return
    loaded = load_research_jobs(
        path=_RESEARCH_JOBS_PATH,
        restart_timestamp=_current_utc_timestamp(),
    )
    _NEXT_JOB_SEQUENCE = loaded.next_job_sequence
    _JOBS.clear()
    for item in loaded.jobs:
        job = _research_job_from_store(item)
        _JOBS[job.id] = job


def _persist_research_jobs_locked() -> None:
    if _RESEARCH_JOBS_PATH is None:
        return
    save_research_jobs(
        path=_RESEARCH_JOBS_PATH,
        jobs=list(_JOBS.values()),
        next_job_sequence=_NEXT_JOB_SEQUENCE,
    )


def _persist_research_jobs_or_500_locked() -> None:
    try:
        _persist_research_jobs_locked()
    except ResearchJobsStoreError as exc:
        raise HTTPException(status_code=500, detail="Research job store failed.") from exc
```

Call `_load_research_jobs_from_store()` after these helpers are defined.

Update mutating request paths:

- In `create_research_job`, after `_prune_finished_jobs_locked()`, call `_persist_research_jobs_or_500_locked()` before submitting to `_JOB_EXECUTOR`.
- In `cancel_research_job`, after `_prune_finished_jobs_locked()`, call `_persist_research_jobs_or_500_locked()` before returning detail.

Update background state changes in `_run_research_job`:

- After setting status to `running`, call `_persist_research_jobs_locked()`.
- After failure state and `_prune_finished_jobs_locked()`, call `_persist_research_jobs_locked()`.
- After success state and `_prune_finished_jobs_locked()`, call `_persist_research_jobs_locked()`.

Update `_prune_finished_jobs_locked()` to leave persistence to callers; do not write inside the prune helper.

- [ ] **Step 4: Run API persistence tests**

Run:

```bash
python -m pytest tests/test_api.py::test_create_research_job_writes_configured_store tests/test_api.py::test_load_research_jobs_from_store_restores_jobs -q
```

Expected: `2 passed`.

## Task 4: Restart Recovery And Safe Store Failure

**Files:**
- Modify: `tests/test_api.py`
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Add API tests**

Append to `tests/test_api.py`:

```python
def test_load_research_jobs_from_store_marks_unfinished_jobs_failed(monkeypatch, tmp_path) -> None:
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
    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", store_path)
    monkeypatch.setattr(api_module, "_current_utc_timestamp", lambda: "2026-04-27T21:00:00Z")
    api_module._JOBS.clear()

    api_module._load_research_jobs_from_store()

    job = api_module._JOBS["job-1"]
    assert job.status == "failed"
    assert job.finished_at == "2026-04-27T21:00:00Z"
    assert job.error == "Research job did not complete before server restart."


def test_create_research_job_returns_safe_500_when_store_write_fails(monkeypatch, tmp_path) -> None:
    store_path = tmp_path / "jobs.json"
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", store_path)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "_persist_research_jobs_locked", lambda: (_ for _ in ()).throw(api_module.ResearchJobsStoreError("secret path")))
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    response = client.post("/research/jobs", json={"query": "Persist me"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Research job store failed."}
    assert "secret path" not in response.text
    assert fake_executor.submissions == []
```

- [ ] **Step 2: Run tests and fix syntax wrapping if needed**

Run:

```bash
python -m pytest tests/test_api.py::test_load_research_jobs_from_store_marks_unfinished_jobs_failed tests/test_api.py::test_create_research_job_returns_safe_500_when_store_write_fails -q
```

Expected: tests pass after Task 3 implementation. If ruff later rejects the long monkeypatch line, rewrite it using a local function that raises `api_module.ResearchJobsStoreError("secret path")`.

## Task 5: Persistence Updates For Completion, Failure, Cancellation, And Pruning

**Files:**
- Modify: `tests/test_api.py`
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Add API tests for persisted state transitions**

Append to `tests/test_api.py`:

```python
def test_run_research_job_updates_configured_store(monkeypatch, tmp_path) -> None:
    store_path = tmp_path / "jobs.json"

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", store_path)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    job_id = client.post("/research/jobs", json={"query": "Persist result"}).json()["job_id"]

    payload = store_path.read_text(encoding="utf-8")
    assert f'"id": "{job_id}"' in payload
    assert '"status": "succeeded"' in payload
    assert '"report_markdown"' in payload


def test_cancel_research_job_updates_configured_store(monkeypatch, tmp_path) -> None:
    store_path = tmp_path / "jobs.json"
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", store_path)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    job_id = client.post("/research/jobs", json={"query": "Cancel"}).json()["job_id"]
    response = client.post(f"/research/jobs/{job_id}/cancel")

    assert response.status_code == 200
    payload = store_path.read_text(encoding="utf-8")
    assert '"status": "cancelled"' in payload


def test_pruned_research_jobs_are_removed_from_configured_store(monkeypatch, tmp_path) -> None:
    store_path = tmp_path / "jobs.json"

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_RESEARCH_JOBS_PATH", store_path)
    monkeypatch.setattr(api_module, "_MAX_RESEARCH_JOBS", 1)
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    first = client.post("/research/jobs", json={"query": "First"}).json()["job_id"]
    second = client.post("/research/jobs", json={"query": "Second"}).json()["job_id"]

    payload = store_path.read_text(encoding="utf-8")
    assert first not in payload
    assert second in payload
```

- [ ] **Step 2: Run transition tests**

Run:

```bash
python -m pytest tests/test_api.py::test_run_research_job_updates_configured_store tests/test_api.py::test_cancel_research_job_updates_configured_store tests/test_api.py::test_pruned_research_jobs_are_removed_from_configured_store -q
```

Expected: `3 passed`. If a test fails because a state transition does not persist, add `_persist_research_jobs_locked()` at the missing transition point inside `_run_research_job()` or the mutating endpoint.

## Task 6: Documentation And Full Verification

**Files:**
- Modify: `docs/configuration.md`
- Modify: `docs/architecture.md`

- [ ] **Step 1: Document configuration**

Add this section to `docs/configuration.md` near other API/runtime settings:

```markdown
### Research Jobs Persistence

`INSIGHT_GRAPH_RESEARCH_JOBS_PATH` enables an opt-in JSON store for API research job metadata. When unset, jobs remain process-local memory only. When set, the API loads job metadata from the configured JSON file at startup and writes job state changes back to that file with atomic replace semantics.

Queued or running jobs from a previous process are restored as failed with `Research job did not complete before server restart.` The API does not automatically resume or rerun unfinished jobs.
```

- [ ] **Step 2: Update architecture wording**

In `docs/architecture.md`, update the `任务追踪` bullet to mention that API jobs can optionally persist metadata to `INSIGHT_GRAPH_RESEARCH_JOBS_PATH` JSON, while still not implementing PostgreSQL checkpoints.

- [ ] **Step 3: Run focused tests**

Run:

```bash
python -m pytest tests/test_research_jobs_store.py tests/test_api.py -q
```

Expected: all store and API tests pass.

- [ ] **Step 4: Run full verification**

Run:

```bash
python -m pytest -q
python -m ruff check .
```

Expected: all tests pass and ruff prints `All checks passed!`.

- [ ] **Step 5: Review diff and commit**

Run:

```bash
git diff -- src/insight_graph/api.py src/insight_graph/research_jobs_store.py tests/test_api.py tests/test_research_jobs_store.py docs/configuration.md docs/architecture.md
git add src/insight_graph/api.py src/insight_graph/research_jobs_store.py tests/test_api.py tests/test_research_jobs_store.py docs/configuration.md docs/architecture.md
git commit -m "feat: persist research job metadata"
```

Expected: commit includes only JSON persistence implementation, tests, and docs.

## Self-Review

- Spec coverage: opt-in env var, stored fields, sequence counter, restart recovery, atomic writes, safe write failure, malformed load failure, no API shape changes, and docs are covered.
- Placeholder scan: no placeholders or deferred implementation steps remain.
- Type consistency: store returns serialized dictionaries; `api.py` owns `ResearchJob` construction and enum conversion.
- Scope check: no SQLite, PostgreSQL, migrations, multi-process locking, auth, WebSocket, or automatic resume behavior is included.
