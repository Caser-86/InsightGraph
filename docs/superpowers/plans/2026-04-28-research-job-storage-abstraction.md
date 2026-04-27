# Research Job Storage Abstraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce an internal storage/backend boundary for research jobs without changing public API behavior.

**Architecture:** Keep `research_jobs.py` as the service layer and API-facing repository module. Add an internal in-memory backend abstraction that owns state containers, locking, copy-on-read, and mutation primitives. Keep JSON persistence and FastAPI response shaping behavior unchanged in the first pass.

**Tech Stack:** Python 3.11+, dataclasses, pytest, ruff, existing FastAPI API layer.

---

## File Structure

- Create: `src/insight_graph/research_jobs_backend.py`
  - Owns `ResearchJobsBackend` protocol and `InMemoryResearchJobsBackend` implementation.
  - Owns internal state: jobs dict, next sequence, lock, active/retained limits.
- Modify: `src/insight_graph/research_jobs.py`
  - Keeps public functions and response builders.
  - Delegates state access and mutation to backend instance.
  - Keeps persistence orchestration for the first pass.
- Modify: `tests/test_research_jobs.py`
  - Adds backend contract tests through public repository functions.
  - Confirms existing public behavior remains unchanged.
- Modify: `tests/test_api.py`
  - Only if API tests expose an integration regression.
- Modify: `docs/research-job-repository-contract.md`
  - Document backend boundary once implemented.

## Task 1: Add Backend State Object Behind Existing Helpers

**Files:**
- Create: `src/insight_graph/research_jobs_backend.py`
- Modify: `src/insight_graph/research_jobs.py`
- Test: `tests/test_research_jobs.py`

- [ ] **Step 1: Write failing backend preservation test**

Add to `tests/test_research_jobs.py`:

```python
def test_research_job_helpers_keep_copy_semantics_after_backend_split() -> None:
    job = jobs_module.ResearchJob(
        id="job-1",
        query="Original",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
    )
    jobs_module.reset_research_jobs_state(jobs=[job])

    inspected = jobs_module.get_research_job_record("job-1")
    assert inspected is not None
    inspected.status = "running"

    stored = jobs_module.get_research_job_record("job-1")
    assert stored is not None
    assert stored.status == "queued"
```

- [ ] **Step 2: Run test to verify current behavior**

Run:

```bash
python -m pytest tests/test_research_jobs.py::test_research_job_helpers_keep_copy_semantics_after_backend_split -v
```

Expected: PASS before refactor. This is a characterization test; keep it green during backend extraction.

- [ ] **Step 3: Create backend file with in-memory state**

Create `src/insight_graph/research_jobs_backend.py`:

```python
from collections.abc import Iterable
from dataclasses import fields, replace
from pathlib import Path
from threading import Lock
from typing import Any

from insight_graph.research_jobs_models import ResearchJob


class InMemoryResearchJobsBackend:
    def __init__(self, *, store_path: Path | None) -> None:
        self.lock = Lock()
        self.max_research_jobs = 100
        self.max_active_research_jobs = 100
        self.next_job_sequence = 0
        self.jobs: dict[str, ResearchJob] = {}
        self.store_path = store_path

    def reset(
        self,
        *,
        next_job_sequence: int = 0,
        store_path: Path | None = None,
        retained_limit: int = 100,
        active_limit: int = 100,
        jobs: Iterable[ResearchJob] = (),
    ) -> None:
        with self.lock:
            self.next_job_sequence = next_job_sequence
            self.store_path = store_path
            self.max_research_jobs = retained_limit
            self.max_active_research_jobs = active_limit
            self.jobs.clear()
            self.jobs.update((job.id, replace(job)) for job in jobs)

    def get(self, job_id: str) -> ResearchJob | None:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                return None
            return replace(job)

    def update(self, job_id: str, **changes: Any) -> ResearchJob | None:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                return None
            valid_fields = {field.name for field in fields(ResearchJob)}
            for name, value in changes.items():
                if name not in valid_fields:
                    raise ValueError(f"Unknown research job field: {name}")
                setattr(job, name, value)
            return replace(job)
```

- [ ] **Step 4: Extract model if needed**

If importing `ResearchJob` from `research_jobs.py` creates a cycle, create `src/insight_graph/research_jobs_models.py`:

```python
from dataclasses import dataclass
from typing import Any

from insight_graph.cli import ResearchPreset

RESEARCH_JOB_STATUS_QUEUED = "queued"


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

Then import and re-export `ResearchJob` from `research_jobs.py` to preserve public imports.

- [ ] **Step 5: Wire helpers through backend**

In `research_jobs.py`, create one backend instance:

```python
_RESEARCH_JOBS_BACKEND = InMemoryResearchJobsBackend(
    store_path=research_jobs_path_from_env()
)
```

Update public helpers:

```python
def reset_research_jobs_state(...):
    _RESEARCH_JOBS_BACKEND.reset(...)

def get_research_job_record(job_id: str) -> ResearchJob | None:
    return _RESEARCH_JOBS_BACKEND.get(job_id)

def update_research_job_record(job_id: str, **changes: Any) -> ResearchJob | None:
    return _RESEARCH_JOBS_BACKEND.update(job_id, **changes)
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
python -m pytest tests/test_research_jobs.py -v
```

Expected: all `tests/test_research_jobs.py` pass.

- [ ] **Step 7: Commit**

```bash
git add src/insight_graph/research_jobs.py src/insight_graph/research_jobs_backend.py src/insight_graph/research_jobs_models.py tests/test_research_jobs.py
git commit -m "refactor: add research job backend boundary"
```

## Task 2: Move Snapshot, Sequence, and Limit Access Behind Backend

**Files:**
- Modify: `src/insight_graph/research_jobs_backend.py`
- Modify: `src/insight_graph/research_jobs.py`
- Test: `tests/test_research_jobs.py`

- [ ] **Step 1: Add failing sequence/limits test**

Add to `tests/test_research_jobs.py`:

```python
def test_research_job_backend_preserves_sequence_and_limits() -> None:
    jobs_module.reset_research_jobs_state(next_job_sequence=4, active_limit=1)
    assert jobs_module.get_next_research_job_sequence() == 4

    created = jobs_module.create_research_job(
        query="First",
        preset=ResearchPreset.offline,
        created_at="2026-04-28T10:00:00Z",
    )
    assert created["status"] == "queued"

    with pytest.raises(jobs_module.HTTPException) as exc_info:
        jobs_module.create_research_job(
            query="Second",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:01Z",
        )
    assert exc_info.value.status_code == 429
```

- [ ] **Step 2: Run test to verify behavior before moving logic**

Run:

```bash
python -m pytest tests/test_research_jobs.py::test_research_job_backend_preserves_sequence_and_limits -v
```

Expected: PASS before refactor.

- [ ] **Step 3: Move active count and pruning helpers into backend**

Add backend methods:

```python
def active_count(self) -> int:
    return sum(job.status in {"queued", "running"} for job in self.jobs.values())

def prune_finished(self) -> None:
    finished_jobs = [
        job for job in self.jobs.values()
        if job.status in {"succeeded", "failed", "cancelled"}
    ]
    overflow = len(finished_jobs) - self.max_research_jobs
    if overflow <= 0:
        return
    for job in sorted(finished_jobs, key=lambda item: item.created_order)[:overflow]:
        del self.jobs[job.id]
```

- [ ] **Step 4: Keep service-layer behavior unchanged**

Update `create_research_job()`, `cancel_research_job()`, and terminal transition functions to call backend methods while keeping response body logic in `research_jobs.py`.

- [ ] **Step 5: Run affected tests**

Run:

```bash
python -m pytest tests/test_research_jobs.py tests/test_api.py -v
```

Expected: all affected tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/research_jobs.py src/insight_graph/research_jobs_backend.py tests/test_research_jobs.py tests/test_api.py
git commit -m "refactor: move research job state helpers to backend"
```

## Task 3: Document Backend Boundary

**Files:**
- Modify: `docs/research-job-repository-contract.md`
- Modify: `docs/roadmap.md`

- [ ] **Step 1: Update contract doc**

Add to `docs/research-job-repository-contract.md`:

```markdown
## Backend boundary

`research_jobs.py` is the service layer. It owns public helper functions, FastAPI-safe error shaping, and response construction. The in-memory backend owns state containers, lock usage, copy-on-read, sequence tracking, active/retained limits, and mutation primitives.

The backend boundary is internal. External callers should continue using `research_jobs.py` public functions.
```

- [ ] **Step 2: Update roadmap**

Change `docs/roadmap.md` item 2 to:

```markdown
2. Clarify repository/storage contract
- Done: stable contract documented in `docs/research-job-repository-contract.md`.
- Done: rollback behavior documented for create/cancel/persist failures.
- Done: storage interface plan saved in `docs/superpowers/plans/2026-04-28-research-job-storage-abstraction.md`.
```

- [ ] **Step 3: Check docs**

Run:

```bash
git diff --check -- docs/research-job-repository-contract.md docs/roadmap.md
```

Expected: no whitespace errors.

- [ ] **Step 4: Commit**

```bash
git add docs/research-job-repository-contract.md docs/roadmap.md
git commit -m "docs: describe research job backend boundary"
```

## Task 4: Final Verification

**Files:**
- No code changes unless verification fails.

- [ ] **Step 1: Run lint**

```bash
python -m ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 2: Run full tests**

```bash
python -m pytest
```

Expected: all tests pass, one skipped test remains acceptable.

- [ ] **Step 3: Push branch**

```bash
git push origin master
```

Expected: remote branch updated; CI starts and passes.

## Self-Review

- Spec coverage: plan preserves endpoint behavior, active cap, retention, queue position, rollback, and future storage requirements.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: `ResearchJob`, `InMemoryResearchJobsBackend`, and helper names match current module naming.
