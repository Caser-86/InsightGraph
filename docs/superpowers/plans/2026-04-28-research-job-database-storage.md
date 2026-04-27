# Research Job Database Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional SQLite-backed research job backend that preserves existing repository/API behavior and keeps the in-memory backend as the default.

**Architecture:** Keep `src/insight_graph/research_jobs.py` as the service layer. Add a focused SQLite backend module below the existing backend seam, plus JSON import helpers and contract tests that run against both in-memory and SQLite backends.

**Tech Stack:** Python 3.11+, stdlib `sqlite3`, dataclasses, pytest, ruff, existing FastAPI/research job service layer.

---

## File Structure

- Create: `src/insight_graph/research_jobs_sqlite_backend.py`
  - Own SQLite schema creation, transaction helper, row serialization, and `SQLiteResearchJobsBackend`.
  - Do not import FastAPI.
- Modify: `src/insight_graph/research_jobs_backend.py`
  - Keep shared status constants and in-memory backend.
  - Add only the narrow shared helper methods required by the service layer.
- Modify: `src/insight_graph/research_jobs.py`
  - Add opt-in backend selection and keep in-memory as default.
  - Keep service-layer response shaping, worker scheduling, safe error policy.
- Modify: `src/insight_graph/research_jobs_store.py`
  - Reuse JSON validation for import from existing metadata store.
- Create: `tests/test_research_jobs_sqlite_backend.py`
  - Test schema, create/cancel/running/terminal semantics, queue position inputs, pruning, rollback behavior.
- Modify: `tests/test_research_jobs.py`
  - Add backend-parametrized contract tests only where public service behavior can run against both backends.
- Modify: `docs/research-job-repository-contract.md`
  - Document optional SQLite backend once implemented.

## Task 1: Add SQLite Schema and Connection Lifecycle

**Files:**
- Create: `src/insight_graph/research_jobs_sqlite_backend.py`
- Create: `tests/test_research_jobs_sqlite_backend.py`

- [ ] **Step 1: Write failing schema initialization test**

Add to `tests/test_research_jobs_sqlite_backend.py`:

```python
import sqlite3

from insight_graph.research_jobs_sqlite_backend import SQLiteResearchJobsBackend


def test_sqlite_backend_initializes_schema_and_sequence(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"

    backend = SQLiteResearchJobsBackend(db_path)
    backend.initialize()

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        sequence = connection.execute(
            "SELECT value FROM research_job_meta WHERE key = 'next_sequence'"
        ).fetchone()

    assert "research_jobs" in tables
    assert "research_job_meta" in tables
    assert sequence == (0,)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_initializes_schema_and_sequence -v`

Expected: FAIL with `ModuleNotFoundError` or missing `SQLiteResearchJobsBackend`.

- [ ] **Step 3: Add minimal SQLite backend schema**

Create `src/insight_graph/research_jobs_sqlite_backend.py`:

```python
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS research_jobs (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    preset TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    created_order INTEGER NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    result_json TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS research_job_meta (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_research_jobs_status_order
ON research_jobs (status, created_order);

CREATE INDEX IF NOT EXISTS idx_research_jobs_created_order
ON research_jobs (created_order);
"""


class SQLiteResearchJobsBackend:
    def __init__(self, path: Path) -> None:
        self._path = path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            connection.execute(
                """
                INSERT OR IGNORE INTO research_job_meta (key, value)
                VALUES ('next_sequence', 0)
                """
            )
            connection.commit()
```

- [ ] **Step 4: Run schema test**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_initializes_schema_and_sequence -v`

Expected: PASS.

- [ ] **Step 5: Commit schema baseline**

```bash
git add src/insight_graph/research_jobs_sqlite_backend.py tests/test_research_jobs_sqlite_backend.py
git commit -m "feat: add research job sqlite schema"
```

## Task 2: Add Serialization Helpers

**Files:**
- Modify: `src/insight_graph/research_jobs_sqlite_backend.py`
- Modify: `tests/test_research_jobs_sqlite_backend.py`

- [ ] **Step 1: Write failing round-trip serialization test**

Add imports:

```python
from insight_graph.cli import ResearchPreset
from insight_graph.research_jobs import ResearchJob
from insight_graph.research_jobs_sqlite_backend import job_from_row, job_to_row
```

Add test:

```python
def test_sqlite_backend_serializes_job_rows(tmp_path) -> None:
    backend = SQLiteResearchJobsBackend(tmp_path / "jobs.sqlite3")
    backend.initialize()
    job = ResearchJob(
        id="job-1",
        query="Compare Cursor",
        preset=ResearchPreset.offline,
        created_order=7,
        created_at="2026-04-28T10:00:00Z",
        status="succeeded",
        started_at="2026-04-28T10:00:01Z",
        finished_at="2026-04-28T10:00:02Z",
        result={"report_markdown": "# Report"},
    )

    with backend._connect() as connection:
        connection.execute(
            """
            INSERT INTO research_jobs (
                id, query, preset, status, created_order, created_at,
                started_at, finished_at, result_json, error
            ) VALUES (
                :id, :query, :preset, :status, :created_order, :created_at,
                :started_at, :finished_at, :result_json, :error
            )
            """,
            job_to_row(job),
        )
        row = connection.execute(
            "SELECT * FROM research_jobs WHERE id = ?",
            ("job-1",),
        ).fetchone()

    assert row is not None
    assert job_from_row(row) == job
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_serializes_job_rows -v`

Expected: FAIL with missing `job_to_row` or `job_from_row`.

- [ ] **Step 3: Add row helpers**

Add to `src/insight_graph/research_jobs_sqlite_backend.py`:

```python
import json
from typing import Any

from insight_graph.cli import ResearchPreset
from insight_graph.research_jobs import ResearchJob


def job_to_row(job: ResearchJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "query": job.query,
        "preset": job.preset.value,
        "status": job.status,
        "created_order": job.created_order,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result_json": json.dumps(job.result) if job.result is not None else None,
        "error": job.error,
    }


def job_from_row(row: sqlite3.Row) -> ResearchJob:
    result_json = row["result_json"]
    return ResearchJob(
        id=row["id"],
        query=row["query"],
        preset=ResearchPreset(row["preset"]),
        created_order=row["created_order"],
        created_at=row["created_at"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        result=json.loads(result_json) if result_json is not None else None,
        error=row["error"],
    )
```

- [ ] **Step 4: Run serialization test**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_serializes_job_rows -v`

Expected: PASS.

- [ ] **Step 5: Commit serialization helpers**

```bash
git add src/insight_graph/research_jobs_sqlite_backend.py tests/test_research_jobs_sqlite_backend.py
git commit -m "feat: serialize research jobs for sqlite"
```

## Task 3: Add Basic State Helpers

**Files:**
- Modify: `src/insight_graph/research_jobs_sqlite_backend.py`
- Modify: `tests/test_research_jobs_sqlite_backend.py`

- [ ] **Step 1: Write failing helper test**

Add test:

```python
def test_sqlite_backend_resets_seeds_gets_and_updates_jobs(tmp_path) -> None:
    backend = SQLiteResearchJobsBackend(tmp_path / "jobs.sqlite3")
    backend.initialize()
    job = ResearchJob(
        id="job-1",
        query="Original",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
    )

    backend.reset(jobs=[job], next_job_sequence=1, retained_limit=3, active_limit=2)
    inspected = backend.get("job-1")
    assert inspected == job
    assert inspected is not job

    inspected.status = "running"
    assert backend.get("job-1") == job

    updated = backend.update("job-1", status="running", started_at="2026-04-28T10:00:01Z")
    assert updated is not None
    assert updated.status == "running"
    assert backend.next_sequence() == 1
    assert backend.retained_limit() == 3
    assert backend.active_limit() == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_resets_seeds_gets_and_updates_jobs -v`

Expected: FAIL with missing `reset`.

- [ ] **Step 3: Add helper methods**

Add fields to `SQLiteResearchJobsBackend.__init__`:

```python
        self._max_research_jobs = 100
        self._max_active_research_jobs = 100
```

Add methods:

```python
from collections.abc import Iterable
from dataclasses import fields, replace


    def reset(
        self,
        *,
        next_job_sequence: int = 0,
        retained_limit: int = 100,
        active_limit: int = 100,
        jobs: Iterable[ResearchJob] = (),
    ) -> None:
        self.initialize()
        self._max_research_jobs = retained_limit
        self._max_active_research_jobs = active_limit
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM research_jobs")
            connection.execute(
                "UPDATE research_job_meta SET value = ? WHERE key = 'next_sequence'",
                (next_job_sequence,),
            )
            connection.executemany(
                """
                INSERT INTO research_jobs (
                    id, query, preset, status, created_order, created_at,
                    started_at, finished_at, result_json, error
                ) VALUES (
                    :id, :query, :preset, :status, :created_order, :created_at,
                    :started_at, :finished_at, :result_json, :error
                )
                """,
                [job_to_row(job) for job in jobs],
            )
            connection.commit()

    def get(self, job_id: str) -> ResearchJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM research_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return job_from_row(row)

    def update(self, job_id: str, **changes: Any) -> ResearchJob | None:
        valid_fields = {field.name for field in fields(ResearchJob)}
        for name in changes:
            if name not in valid_fields:
                raise ValueError(f"Unknown research job field: {name}")
        current = self.get(job_id)
        if current is None:
            return None
        updated = replace(current, **changes)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE research_jobs
                SET query = :query,
                    preset = :preset,
                    status = :status,
                    created_order = :created_order,
                    created_at = :created_at,
                    started_at = :started_at,
                    finished_at = :finished_at,
                    result_json = :result_json,
                    error = :error
                WHERE id = :id
                """,
                job_to_row(updated),
            )
            connection.commit()
        return updated

    def next_sequence(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM research_job_meta WHERE key = 'next_sequence'"
            ).fetchone()
        return int(row["value"])

    def retained_limit(self) -> int:
        return self._max_research_jobs

    def active_limit(self) -> int:
        return self._max_active_research_jobs
```

- [ ] **Step 4: Run helper test**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_resets_seeds_gets_and_updates_jobs -v`

Expected: PASS.

- [ ] **Step 5: Commit basic helpers**

```bash
git add src/insight_graph/research_jobs_sqlite_backend.py tests/test_research_jobs_sqlite_backend.py
git commit -m "feat: add sqlite research job state helpers"
```

## Task 4: Add Active Count, Pruning, Snapshot, Restore

**Files:**
- Modify: `src/insight_graph/research_jobs_sqlite_backend.py`
- Modify: `tests/test_research_jobs_sqlite_backend.py`

- [ ] **Step 1: Write failing state helper tests**

Add tests:

```python
def test_sqlite_backend_counts_active_jobs_and_prunes_terminal_jobs(tmp_path) -> None:
    backend = SQLiteResearchJobsBackend(tmp_path / "jobs.sqlite3")
    backend.initialize()
    backend.reset(
        retained_limit=1,
        jobs=[
            ResearchJob(id="old", query="Old", preset=ResearchPreset.offline, created_order=1, created_at="2026-04-28T10:00:00Z", status="succeeded"),
            ResearchJob(id="queued", query="Queued", preset=ResearchPreset.offline, created_order=2, created_at="2026-04-28T10:00:01Z"),
            ResearchJob(id="running", query="Running", preset=ResearchPreset.offline, created_order=3, created_at="2026-04-28T10:00:02Z", status="running"),
            ResearchJob(id="new", query="New", preset=ResearchPreset.offline, created_order=4, created_at="2026-04-28T10:00:03Z", status="failed"),
        ],
    )

    assert backend.active_count() == 2
    backend.prune_finished()

    assert backend.get("old") is None
    assert backend.get("queued") is not None
    assert backend.get("running") is not None
    assert backend.get("new") is not None


def test_sqlite_backend_snapshot_restores_jobs_and_sequence(tmp_path) -> None:
    backend = SQLiteResearchJobsBackend(tmp_path / "jobs.sqlite3")
    backend.initialize()
    original = ResearchJob(
        id="job-1",
        query="Original",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
    )
    backend.reset(next_job_sequence=1, jobs=[original])
    snapshot = backend.snapshot()

    backend.reset(next_job_sequence=2)
    backend.restore(snapshot)

    assert backend.next_sequence() == 1
    assert backend.get("job-1") == original
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_counts_active_jobs_and_prunes_terminal_jobs tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_snapshot_restores_jobs_and_sequence -v`

Expected: FAIL with missing methods.

- [ ] **Step 3: Implement state helpers**

Add import:

```python
from insight_graph.research_jobs_backend import (
    ACTIVE_RESEARCH_JOB_STATUSES,
    TERMINAL_RESEARCH_JOB_STATUSES,
    ResearchJobsBackendSnapshot,
)
```

Add methods:

```python
    def active_count(self) -> int:
        placeholders = ",".join("?" for _ in ACTIVE_RESEARCH_JOB_STATUSES)
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM research_jobs WHERE status IN ({placeholders})",
                tuple(ACTIVE_RESEARCH_JOB_STATUSES),
            ).fetchone()
        return int(row["count"])

    def prune_finished(self) -> None:
        placeholders = ",".join("?" for _ in TERMINAL_RESEARCH_JOB_STATUSES)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                f"""
                SELECT id FROM research_jobs
                WHERE status IN ({placeholders})
                ORDER BY created_order ASC
                """,
                tuple(TERMINAL_RESEARCH_JOB_STATUSES),
            ).fetchall()
            overflow = len(rows) - self._max_research_jobs
            if overflow > 0:
                connection.executemany(
                    "DELETE FROM research_jobs WHERE id = ?",
                    [(row["id"],) for row in rows[:overflow]],
                )
            connection.commit()

    def snapshot(self) -> ResearchJobsBackendSnapshot:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM research_jobs").fetchall()
        return ResearchJobsBackendSnapshot(
            next_job_sequence=self.next_sequence(),
            jobs={job.id: job for job in (job_from_row(row) for row in rows)},
        )

    def restore(self, snapshot: ResearchJobsBackendSnapshot) -> None:
        self.reset(
            next_job_sequence=snapshot.next_job_sequence,
            retained_limit=self._max_research_jobs,
            active_limit=self._max_active_research_jobs,
            jobs=snapshot.jobs.values(),
        )
```

- [ ] **Step 4: Run state helper tests**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_counts_active_jobs_and_prunes_terminal_jobs tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_snapshot_restores_jobs_and_sequence -v`

Expected: PASS.

- [ ] **Step 5: Commit state helpers**

```bash
git add src/insight_graph/research_jobs_sqlite_backend.py tests/test_research_jobs_sqlite_backend.py
git commit -m "feat: add sqlite research job state snapshots"
```

## Task 5: Add Atomic Create/Cancel/Running/Terminal Backend Operations

**Files:**
- Modify: `src/insight_graph/research_jobs_sqlite_backend.py`
- Modify: `tests/test_research_jobs_sqlite_backend.py`

- [ ] **Step 1: Write failing transaction tests**

Add tests:

```python
def test_sqlite_backend_create_job_is_atomic_with_active_limit(tmp_path) -> None:
    backend = SQLiteResearchJobsBackend(tmp_path / "jobs.sqlite3")
    backend.initialize()
    backend.reset(active_limit=1)

    created = backend.create_job(
        job_id="job-1",
        query="First",
        preset=ResearchPreset.offline,
        created_at="2026-04-28T10:00:00Z",
    )

    assert created.created_order == 1
    assert backend.next_sequence() == 1

    with pytest.raises(ValueError, match="Too many active research jobs"):
        backend.create_job(
            job_id="job-2",
            query="Second",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:01Z",
        )
    assert backend.get("job-2") is None
    assert backend.next_sequence() == 1


def test_sqlite_backend_cancel_and_running_transitions_are_guarded(tmp_path) -> None:
    backend = SQLiteResearchJobsBackend(tmp_path / "jobs.sqlite3")
    backend.initialize()
    backend.reset(jobs=[ResearchJob(id="job-1", query="Queued", preset=ResearchPreset.offline, created_order=1, created_at="2026-04-28T10:00:00Z")])

    cancelled = backend.cancel_queued("job-1", finished_at="2026-04-28T10:00:01Z")
    assert cancelled is not None
    assert cancelled.status == "cancelled"

    assert backend.mark_running("job-1", started_at="2026-04-28T10:00:02Z") is None


def test_sqlite_backend_terminal_update_is_best_effort_compatible(tmp_path) -> None:
    backend = SQLiteResearchJobsBackend(tmp_path / "jobs.sqlite3")
    backend.initialize()
    job = ResearchJob(id="job-1", query="Running", preset=ResearchPreset.offline, created_order=1, created_at="2026-04-28T10:00:00Z", status="running")
    backend.reset(jobs=[job])

    updated = backend.mark_terminal(
        "job-1",
        status="succeeded",
        finished_at="2026-04-28T10:00:03Z",
        result={"report_markdown": "# Report"},
        error=None,
    )

    assert updated is not None
    assert updated.status == "succeeded"
    assert updated.result == {"report_markdown": "# Report"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py -v`

Expected: FAIL with missing transaction methods.

- [ ] **Step 3: Implement transaction methods**

Add methods:

```python
    def create_job(
        self,
        *,
        job_id: str,
        query: str,
        preset: ResearchPreset,
        created_at: str,
    ) -> ResearchJob:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            active = connection.execute(
                "SELECT COUNT(*) AS count FROM research_jobs WHERE status IN ('queued', 'running')"
            ).fetchone()["count"]
            if active >= self._max_active_research_jobs:
                connection.rollback()
                raise ValueError("Too many active research jobs")
            next_sequence = connection.execute(
                "SELECT value FROM research_job_meta WHERE key = 'next_sequence'"
            ).fetchone()["value"] + 1
            connection.execute(
                "UPDATE research_job_meta SET value = ? WHERE key = 'next_sequence'",
                (next_sequence,),
            )
            job = ResearchJob(
                id=job_id,
                query=query,
                preset=preset,
                created_order=next_sequence,
                created_at=created_at,
            )
            connection.execute(
                """
                INSERT INTO research_jobs (
                    id, query, preset, status, created_order, created_at,
                    started_at, finished_at, result_json, error
                ) VALUES (
                    :id, :query, :preset, :status, :created_order, :created_at,
                    :started_at, :finished_at, :result_json, :error
                )
                """,
                job_to_row(job),
            )
            connection.commit()
        self.prune_finished()
        return job

    def cancel_queued(self, job_id: str, *, finished_at: str) -> ResearchJob | None:
        current = self.get(job_id)
        if current is None:
            return None
        if current.status != "queued":
            raise ValueError("Only queued research jobs can be cancelled")
        return self.update(job_id, status="cancelled", finished_at=finished_at)

    def mark_running(self, job_id: str, *, started_at: str) -> ResearchJob | None:
        current = self.get(job_id)
        if current is None or current.status == "cancelled":
            return None
        if current.status != "queued":
            raise ValueError("Only queued research jobs can start running")
        return self.update(job_id, status="running", started_at=started_at)

    def mark_terminal(
        self,
        job_id: str,
        *,
        status: str,
        finished_at: str,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> ResearchJob | None:
        if status not in TERMINAL_RESEARCH_JOB_STATUSES:
            raise ValueError(f"Invalid terminal status: {status}")
        updated = self.update(
            job_id,
            status=status,
            finished_at=finished_at,
            result=result,
            error=error,
        )
        self.prune_finished()
        return updated
```

- [ ] **Step 4: Run transaction tests**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py -v`

Expected: PASS.

- [ ] **Step 5: Commit transaction methods**

```bash
git add src/insight_graph/research_jobs_sqlite_backend.py tests/test_research_jobs_sqlite_backend.py
git commit -m "feat: add sqlite research job transactions"
```

## Task 6: Add JSON Import Helper

**Files:**
- Modify: `src/insight_graph/research_jobs_sqlite_backend.py`
- Modify: `tests/test_research_jobs_sqlite_backend.py`

- [ ] **Step 1: Write failing import test**

Add imports:

```python
import json
```

Add test:

```python
def test_sqlite_backend_imports_valid_json_store_atomically(tmp_path) -> None:
    json_path = tmp_path / "jobs.json"
    json_path.write_text(
        json.dumps(
            {
                "next_job_sequence": 4,
                "jobs": [
                    {
                        "id": "job-1",
                        "query": "Compare Cursor",
                        "preset": "offline",
                        "created_order": 4,
                        "created_at": "2026-04-28T10:00:00Z",
                        "status": "succeeded",
                        "started_at": "2026-04-28T10:00:01Z",
                        "finished_at": "2026-04-28T10:00:02Z",
                        "result": {"report_markdown": "# Report"},
                        "error": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    backend = SQLiteResearchJobsBackend(tmp_path / "jobs.sqlite3")
    backend.import_json_store(json_path, restart_timestamp="2026-04-28T11:00:00Z")

    assert backend.next_sequence() == 4
    imported = backend.get("job-1")
    assert imported is not None
    assert imported.status == "succeeded"
    assert imported.result == {"report_markdown": "# Report"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_imports_valid_json_store_atomically -v`

Expected: FAIL with missing `import_json_store`.

- [ ] **Step 3: Implement JSON import**

Add imports:

```python
from insight_graph.research_jobs_store import load_research_jobs
```

Add method:

```python
    def import_json_store(self, path: Path, *, restart_timestamp: str) -> None:
        loaded = load_research_jobs(path=path, restart_timestamp=restart_timestamp)
        jobs = [
            ResearchJob(
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
            for item in loaded.jobs
        ]
        self.reset(next_job_sequence=loaded.next_job_sequence, jobs=jobs)
```

- [ ] **Step 4: Run import test**

Run: `python -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_imports_valid_json_store_atomically -v`

Expected: PASS.

- [ ] **Step 5: Commit import helper**

```bash
git add src/insight_graph/research_jobs_sqlite_backend.py tests/test_research_jobs_sqlite_backend.py
git commit -m "feat: import research job json store into sqlite"
```

## Task 7: Wire Optional Backend Selection

**Files:**
- Modify: `src/insight_graph/research_jobs.py`
- Modify: `tests/test_research_jobs.py`

- [ ] **Step 1: Write failing selection test**

Add test to `tests/test_research_jobs.py`:

```python
def test_configure_research_jobs_sqlite_backend_preserves_public_behavior(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"

    jobs_module.configure_research_jobs_sqlite_backend(db_path)
    try:
        created = jobs_module.create_research_job(
            query="SQLite",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )
        listed = jobs_module.list_research_jobs(status=None, limit=10)
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()

    assert created["status"] == "queued"
    assert listed["count"] == 1
    assert listed["jobs"][0]["query"] == "SQLite"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_research_jobs.py::test_configure_research_jobs_sqlite_backend_preserves_public_behavior -v`

Expected: FAIL with missing `configure_research_jobs_sqlite_backend`.

- [ ] **Step 3: Add backend query helpers used by the service layer**

Add to `InMemoryResearchJobsBackend` in `src/insight_graph/research_jobs_backend.py`:

```python
    def all_jobs(self) -> list[Any]:
        with self._lock:
            return [replace(job) for job in self._jobs.values()]
```

Add to `SQLiteResearchJobsBackend` in `src/insight_graph/research_jobs_sqlite_backend.py`:

```python
    def all_jobs(self) -> list[ResearchJob]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM research_jobs ORDER BY created_order DESC"
            ).fetchall()
        return [job_from_row(row) for row in rows]
```

- [ ] **Step 4: Add backend configuration functions**

Add import to `src/insight_graph/research_jobs.py`:

```python
from insight_graph.research_jobs_sqlite_backend import SQLiteResearchJobsBackend
```

Add functions near maintenance helpers:

```python
def configure_research_jobs_in_memory_backend() -> None:
    global _RESEARCH_JOBS_BACKEND

    reset_research_jobs_state()
    _RESEARCH_JOBS_BACKEND = InMemoryResearchJobsBackend(
        store_path=_RESEARCH_JOBS_PATH,
        jobs=_JOBS,
        lock=_JOBS_LOCK,
    )


def configure_research_jobs_sqlite_backend(path: Path) -> None:
    global _RESEARCH_JOBS_BACKEND, _NEXT_JOB_SEQUENCE

    backend = SQLiteResearchJobsBackend(path)
    backend.initialize()
    _RESEARCH_JOBS_BACKEND = backend
    _NEXT_JOB_SEQUENCE = backend.next_sequence()
```

- [ ] **Step 5: Route create/list/cancel reads through the selected backend**

Add helpers to `src/insight_graph/research_jobs.py`:

```python
def _all_research_jobs_locked() -> list[ResearchJob]:
    return _RESEARCH_JOBS_BACKEND.all_jobs()


def _get_research_job_locked(job_id: str) -> ResearchJob | None:
    return _RESEARCH_JOBS_BACKEND.get(job_id)
```

Update `_queued_job_positions_locked()`:

```python
def _queued_job_positions_locked() -> dict[str, int]:
    queued_jobs = sorted(
        (
            job
            for job in _all_research_jobs_locked()
            if job.status == RESEARCH_JOB_STATUS_QUEUED
        ),
        key=lambda item: item.created_order,
    )
    return {job.id: index for index, job in enumerate(queued_jobs, start=1)}
```

Update `_jobs_list_response_locked()` job source:

```python
    jobs = sorted(
        _all_research_jobs_locked(),
        key=lambda item: item.created_order,
        reverse=True,
    )
```

Update `_jobs_summary_response_locked()` loops to use `_all_research_jobs_locked()` once:

```python
    all_jobs = _all_research_jobs_locked()
    counts = {status: 0 for status in RESEARCH_JOB_STATUSES}
    for job in all_jobs:
        counts[job.status] = counts.get(job.status, 0) + 1
    counts["total"] = len(all_jobs)

    queued_positions = _queued_job_positions_locked()
    queued_jobs = sorted(
        (job for job in all_jobs if job.status == RESEARCH_JOB_STATUS_QUEUED),
        key=lambda item: item.created_order,
    )
    running_jobs = sorted(
        (job for job in all_jobs if job.status == RESEARCH_JOB_STATUS_RUNNING),
        key=lambda item: item.created_order,
    )
```

Update `create_research_job()` before the existing in-memory path:

```python
        if isinstance(_RESEARCH_JOBS_BACKEND, SQLiteResearchJobsBackend):
            try:
                job = _RESEARCH_JOBS_BACKEND.create_job(
                    job_id=str(uuid4()),
                    query=query,
                    preset=preset,
                    created_at=created_at,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=429,
                    detail="Too many active research jobs.",
                ) from exc
            _NEXT_JOB_SEQUENCE = _RESEARCH_JOBS_BACKEND.next_sequence()
            return _job_create_response(job)
```

Update `cancel_research_job()` before the existing in-memory path:

```python
        if isinstance(_RESEARCH_JOBS_BACKEND, SQLiteResearchJobsBackend):
            try:
                job = _RESEARCH_JOBS_BACKEND.cancel_queued(
                    job_id,
                    finished_at=finished_at,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=409,
                    detail="Only queued research jobs can be cancelled.",
                ) from exc
            if job is None:
                raise HTTPException(status_code=404, detail="Research job not found.")
            return _job_detail(job, _queued_job_positions_locked())
```

Update `get_research_job()` job lookup:

```python
        job = _get_research_job_locked(job_id)
```

- [ ] **Step 6: Run selection test**

Run: `python -m pytest tests/test_research_jobs.py::test_configure_research_jobs_sqlite_backend_preserves_public_behavior -v`

Expected: PASS.

- [ ] **Step 7: Commit optional backend selection**

```bash
git add src/insight_graph/research_jobs.py tests/test_research_jobs.py
git commit -m "feat: allow sqlite research job backend selection"
```

## Task 8: Add Contract Tests and Docs

**Files:**
- Modify: `tests/test_research_jobs.py`
- Modify: `docs/research-job-repository-contract.md`

- [ ] **Step 1: Add backend contract test marker**

Add a parametrized fixture in `tests/test_research_jobs.py`:

```python
@pytest.fixture(params=["memory", "sqlite"])
def research_jobs_backend(request, tmp_path):
    if request.param == "sqlite":
        jobs_module.configure_research_jobs_sqlite_backend(tmp_path / "jobs.sqlite3")
    else:
        jobs_module.configure_research_jobs_in_memory_backend()
    try:
        yield request.param
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()
```

Add contract test:

```python
def test_research_jobs_backend_contract_create_list_cancel(research_jobs_backend) -> None:
    created = jobs_module.create_research_job(
        query="Contract",
        preset=ResearchPreset.offline,
        created_at="2026-04-28T10:00:00Z",
    )
    assert created["status"] == "queued"

    listed = jobs_module.list_research_jobs(status=None, limit=10)
    assert listed["count"] == 1
    assert listed["jobs"][0]["queue_position"] == 1

    cancelled = jobs_module.cancel_research_job(
        created["job_id"],
        finished_at="2026-04-28T10:00:01Z",
    )
    assert cancelled["status"] == "cancelled"
    assert "queue_position" not in cancelled
```

- [ ] **Step 2: Run contract test**

Run: `python -m pytest tests/test_research_jobs.py::test_research_jobs_backend_contract_create_list_cancel -v`

Expected: PASS for both `memory` and `sqlite` params.

- [ ] **Step 3: Update docs**

Add to `docs/research-job-repository-contract.md` under `Service/backend boundary`:

```markdown
- SQLite storage is optional and must preserve the same public repository contract as the in-memory backend.
- SQLite does not add retry/resume, worker leasing, distributed locks, or public API changes.
```

- [ ] **Step 4: Verify docs and tests**

Run:

```bash
git diff --check
python -m pytest tests/test_research_jobs_sqlite_backend.py tests/test_research_jobs.py
python -m ruff check .
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit contract tests and docs**

```bash
git add tests/test_research_jobs.py docs/research-job-repository-contract.md
git commit -m "test: cover sqlite research job backend contract"
```

## Final Verification

Run:

```bash
python -m pytest
python -m ruff check .
git status --short --branch
```

Expected:

- `pytest`: all tests pass, existing skip count unchanged unless new environment-specific skips are added intentionally.
- `ruff`: no issues.
- `git status`: clean branch after final commit.
