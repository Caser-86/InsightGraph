# SQLite Research Job Worker Leasing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SQLite-only research job worker leasing so multiple API processes can avoid double-starting jobs and abandoned running jobs requeue after lease expiry.

**Architecture:** Store lease metadata on `research_jobs` rows. SQLite backend owns claim, reclaim, heartbeat, and ownership-aware terminal writes. Service/API layers use the lease path only for SQLite while preserving existing in-memory behavior and public response shapes.

**Tech Stack:** Python 3.13 local, Python 3.11 CI, FastAPI, sqlite3, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/research_jobs_sqlite_backend.py`: schema migration, lease columns, SQLite claim/heartbeat/reclaim/terminal ownership helpers.
- Modify `src/insight_graph/research_jobs.py`: process worker ID, lease timing constants, SQLite-aware running/heartbeat/terminal service helpers.
- Modify `src/insight_graph/api.py`: run SQLite jobs through lease claim and a heartbeat loop while preserving current API responses.
- Modify `tests/test_research_jobs_sqlite_backend.py`: focused SQLite lease and migration tests.
- Modify `tests/test_research_jobs.py`: service-level SQLite lease tests and unchanged memory backend contract coverage.
- Modify `tests/test_api.py`: smoke test that SQLite-backed job execution completes and does not expose lease metadata.
- Modify `docs/research-job-repository-contract.md`: document internal SQLite lease semantics.
- Modify `docs/roadmap.md`: mark worker leasing implementation progress after completion.

## Task 1: SQLite Schema Migration

**Files:**
- Modify: `tests/test_research_jobs_sqlite_backend.py`
- Modify: `src/insight_graph/research_jobs_sqlite_backend.py`

- [ ] **Step 1: Write failing schema and migration tests**

Append these tests to `tests/test_research_jobs_sqlite_backend.py`:

```python
def sqlite_columns(db_path, table_name: str) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})")}


def test_sqlite_backend_initializes_lease_columns(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"

    backend = SQLiteResearchJobsBackend(db_path)
    backend.initialize()

    assert {
        "worker_id",
        "lease_expires_at",
        "heartbeat_at",
        "attempt_count",
    }.issubset(sqlite_columns(db_path, "research_jobs"))


def test_sqlite_backend_migrates_existing_database_with_missing_lease_columns(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE research_jobs (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                preset TEXT NOT NULL,
                status TEXT NOT NULL,
                created_order INTEGER NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                result_json TEXT,
                error TEXT
            );
            CREATE TABLE research_job_meta (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            );
            INSERT INTO research_job_meta (key, value) VALUES ('next_sequence', 0);
            """
        )

    backend = SQLiteResearchJobsBackend(db_path)
    backend.initialize()

    assert {
        "worker_id",
        "lease_expires_at",
        "heartbeat_at",
        "attempt_count",
    }.issubset(sqlite_columns(db_path, "research_jobs"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_initializes_lease_columns tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_migrates_existing_database_with_missing_lease_columns -v
```

Expected: FAIL because the lease columns do not exist.

- [ ] **Step 3: Implement schema columns and migration helper**

In `src/insight_graph/research_jobs_sqlite_backend.py`, update `SCHEMA` so `research_jobs` includes the new columns after `error TEXT`:

```sql
    error TEXT,
    worker_id TEXT,
    lease_expires_at TEXT,
    heartbeat_at TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0
```

Add this helper near the top-level row helpers:

```python
def ensure_lease_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(research_jobs)")
    }
    migrations = {
        "worker_id": "ALTER TABLE research_jobs ADD COLUMN worker_id TEXT",
        "lease_expires_at": "ALTER TABLE research_jobs ADD COLUMN lease_expires_at TEXT",
        "heartbeat_at": "ALTER TABLE research_jobs ADD COLUMN heartbeat_at TEXT",
        "attempt_count": "ALTER TABLE research_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0",
    }
    for column_name, statement in migrations.items():
        if column_name not in existing_columns:
            connection.execute(statement)
```

Call it in `SQLiteResearchJobsBackend.initialize()` immediately after `connection.executescript(SCHEMA)`:

```python
            ensure_lease_columns(connection)
```

- [ ] **Step 4: Include lease metadata in insert/update row bindings**

Update `job_to_row()` to include lease defaults:

```python
        "worker_id": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
        "attempt_count": 0,
```

Update every explicit `INSERT INTO research_jobs` column list in `reset()`, `seed()`, and `create_job()` to include:

```sql
                    worker_id, lease_expires_at, heartbeat_at, attempt_count
```

Update their `VALUES` lists to include:

```sql
                    :worker_id, :lease_expires_at, :heartbeat_at, :attempt_count
```

Do not add lease fields to `ResearchJob`; keep them internal to SQLite rows.

- [ ] **Step 5: Run schema tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_initializes_lease_columns tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_migrates_existing_database_with_missing_lease_columns -v
```

Expected: PASS.

- [ ] **Step 6: Commit schema migration**

```powershell
git add src/insight_graph/research_jobs_sqlite_backend.py tests/test_research_jobs_sqlite_backend.py
git commit -m "feat: add sqlite research job lease columns"
```

## Task 2: SQLite Lease Backend Helpers

**Files:**
- Modify: `tests/test_research_jobs_sqlite_backend.py`
- Modify: `src/insight_graph/research_jobs_sqlite_backend.py`

- [ ] **Step 1: Write failing claim and heartbeat tests**

Append these tests to `tests/test_research_jobs_sqlite_backend.py`:

```python
def sqlite_job_row(db_path, job_id: str):
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT * FROM research_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()


def test_sqlite_backend_claims_queued_job_for_worker(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    backend = SQLiteResearchJobsBackend(db_path)
    backend.initialize()
    backend.reset(
        jobs=[
            ResearchJob(
                id="job-1",
                query="Claim",
                preset=ResearchPreset.offline,
                created_order=1,
                created_at="2026-04-28T10:00:00Z",
            )
        ]
    )

    claimed = backend.claim_for_worker(
        "job-1",
        worker_id="worker-a",
        now="2026-04-28T10:00:01Z",
        lease_expires_at="2026-04-28T10:05:01Z",
    )

    assert claimed is not None
    assert claimed.status == "running"
    assert claimed.started_at == "2026-04-28T10:00:01Z"
    row = sqlite_job_row(db_path, "job-1")
    assert row["worker_id"] == "worker-a"
    assert row["heartbeat_at"] == "2026-04-28T10:00:01Z"
    assert row["lease_expires_at"] == "2026-04-28T10:05:01Z"
    assert row["attempt_count"] == 1


def test_sqlite_backend_refuses_active_lease_from_another_worker(tmp_path) -> None:
    backend = SQLiteResearchJobsBackend(tmp_path / "jobs.sqlite3")
    backend.initialize()
    backend.reset(
        jobs=[
            ResearchJob(
                id="job-1",
                query="Claim",
                preset=ResearchPreset.offline,
                created_order=1,
                created_at="2026-04-28T10:00:00Z",
            )
        ]
    )
    assert backend.claim_for_worker(
        "job-1",
        worker_id="worker-a",
        now="2026-04-28T10:00:01Z",
        lease_expires_at="2026-04-28T10:05:01Z",
    ) is not None

    assert backend.claim_for_worker(
        "job-1",
        worker_id="worker-b",
        now="2026-04-28T10:01:00Z",
        lease_expires_at="2026-04-28T10:06:00Z",
    ) is None


def test_sqlite_backend_heartbeat_extends_owned_lease(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    backend = SQLiteResearchJobsBackend(db_path)
    backend.initialize()
    backend.reset(
        jobs=[
            ResearchJob(
                id="job-1",
                query="Heartbeat",
                preset=ResearchPreset.offline,
                created_order=1,
                created_at="2026-04-28T10:00:00Z",
            )
        ]
    )
    backend.claim_for_worker(
        "job-1",
        worker_id="worker-a",
        now="2026-04-28T10:00:01Z",
        lease_expires_at="2026-04-28T10:05:01Z",
    )

    assert backend.heartbeat(
        "job-1",
        worker_id="worker-a",
        now="2026-04-28T10:01:01Z",
        lease_expires_at="2026-04-28T10:06:01Z",
    ) is True
    row = sqlite_job_row(db_path, "job-1")
    assert row["heartbeat_at"] == "2026-04-28T10:01:01Z"
    assert row["lease_expires_at"] == "2026-04-28T10:06:01Z"


def test_sqlite_backend_heartbeat_rejects_non_owner(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    backend = SQLiteResearchJobsBackend(db_path)
    backend.initialize()
    backend.reset(
        jobs=[
            ResearchJob(
                id="job-1",
                query="Heartbeat",
                preset=ResearchPreset.offline,
                created_order=1,
                created_at="2026-04-28T10:00:00Z",
            )
        ]
    )
    backend.claim_for_worker(
        "job-1",
        worker_id="worker-a",
        now="2026-04-28T10:00:01Z",
        lease_expires_at="2026-04-28T10:05:01Z",
    )

    assert backend.heartbeat(
        "job-1",
        worker_id="worker-b",
        now="2026-04-28T10:01:01Z",
        lease_expires_at="2026-04-28T10:06:01Z",
    ) is False
    row = sqlite_job_row(db_path, "job-1")
    assert row["worker_id"] == "worker-a"
    assert row["heartbeat_at"] == "2026-04-28T10:00:01Z"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_claims_queued_job_for_worker tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_refuses_active_lease_from_another_worker tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_heartbeat_extends_owned_lease tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_heartbeat_rejects_non_owner -v
```

Expected: FAIL because `claim_for_worker()` and `heartbeat()` do not exist.

- [ ] **Step 3: Implement reclaim, claim, and heartbeat**

Add these methods inside `SQLiteResearchJobsBackend` after `cancel_queued()`:

```python
    def _requeue_expired_running(
        self,
        connection: sqlite3.Connection,
        *,
        now: str,
    ) -> None:
        connection.execute(
            """
            UPDATE research_jobs
            SET status = 'queued',
                worker_id = NULL,
                lease_expires_at = NULL,
                heartbeat_at = NULL,
                result_json = NULL,
                error = NULL
            WHERE status = 'running'
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at < ?
            """,
            (now,),
        )

    def claim_for_worker(
        self,
        job_id: str,
        *,
        worker_id: str,
        now: str,
        lease_expires_at: str,
    ) -> ResearchJob | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._requeue_expired_running(connection, now=now)
            current = connection.execute(
                "SELECT * FROM research_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if current is None or current["status"] != "queued":
                connection.rollback()
                return None
            started_at = current["started_at"] or now
            connection.execute(
                """
                UPDATE research_jobs
                SET status = 'running',
                    started_at = ?,
                    worker_id = ?,
                    heartbeat_at = ?,
                    lease_expires_at = ?,
                    attempt_count = attempt_count + 1
                WHERE id = ? AND status = 'queued'
                """,
                (started_at, worker_id, now, lease_expires_at, job_id),
            )
            connection.commit()
        return self.get(job_id)

    def heartbeat(
        self,
        job_id: str,
        *,
        worker_id: str,
        now: str,
        lease_expires_at: str,
    ) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE research_jobs
                SET heartbeat_at = ?, lease_expires_at = ?
                WHERE id = ? AND worker_id = ? AND status = 'running'
                """,
                (now, lease_expires_at, job_id, worker_id),
            )
            connection.commit()
        return cursor.rowcount == 1
```

- [ ] **Step 4: Run claim and heartbeat tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_claims_queued_job_for_worker tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_refuses_active_lease_from_another_worker tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_heartbeat_extends_owned_lease tests/test_research_jobs_sqlite_backend.py::test_sqlite_backend_heartbeat_rejects_non_owner -v
```

Expected: PASS.

- [ ] **Step 5: Write failing reclaim and terminal ownership tests**

Append these tests to `tests/test_research_jobs_sqlite_backend.py`:

```python
def test_sqlite_backend_claim_requeues_expired_running_job(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    backend = SQLiteResearchJobsBackend(db_path)
    backend.initialize()
    backend.reset(
        jobs=[
            ResearchJob(
                id="job-1",
                query="Expired",
                preset=ResearchPreset.offline,
                created_order=1,
                created_at="2026-04-28T10:00:00Z",
            )
        ]
    )
    backend.claim_for_worker(
        "job-1",
        worker_id="worker-a",
        now="2026-04-28T10:00:01Z",
        lease_expires_at="2026-04-28T10:05:01Z",
    )

    claimed = backend.claim_for_worker(
        "job-1",
        worker_id="worker-b",
        now="2026-04-28T10:05:02Z",
        lease_expires_at="2026-04-28T10:10:02Z",
    )

    assert claimed is not None
    assert claimed.status == "running"
    assert claimed.started_at == "2026-04-28T10:00:01Z"
    row = sqlite_job_row(db_path, "job-1")
    assert row["worker_id"] == "worker-b"
    assert row["attempt_count"] == 2


def test_sqlite_backend_terminal_update_requires_owner(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    backend = SQLiteResearchJobsBackend(db_path)
    backend.initialize()
    backend.reset(
        jobs=[
            ResearchJob(
                id="job-1",
                query="Terminal",
                preset=ResearchPreset.offline,
                created_order=1,
                created_at="2026-04-28T10:00:00Z",
            )
        ]
    )
    backend.claim_for_worker(
        "job-1",
        worker_id="worker-a",
        now="2026-04-28T10:00:01Z",
        lease_expires_at="2026-04-28T10:05:01Z",
    )

    assert backend.mark_terminal_for_worker(
        "job-1",
        worker_id="worker-b",
        status="succeeded",
        finished_at="2026-04-28T10:00:03Z",
        result={"report_markdown": "# Wrong"},
        error=None,
    ) is None

    updated = backend.mark_terminal_for_worker(
        "job-1",
        worker_id="worker-a",
        status="succeeded",
        finished_at="2026-04-28T10:00:04Z",
        result={"report_markdown": "# Right"},
        error=None,
    )

    assert updated is not None
    assert updated.status == "succeeded"
    assert updated.result == {"report_markdown": "# Right"}
    row = sqlite_job_row(db_path, "job-1")
    assert row["worker_id"] is None
    assert row["lease_expires_at"] is None
    assert row["heartbeat_at"] is None


def test_sqlite_backend_stale_terminal_does_not_overwrite_new_attempt(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    backend = SQLiteResearchJobsBackend(db_path)
    backend.initialize()
    backend.reset(
        jobs=[
            ResearchJob(
                id="job-1",
                query="Stale",
                preset=ResearchPreset.offline,
                created_order=1,
                created_at="2026-04-28T10:00:00Z",
            )
        ]
    )
    backend.claim_for_worker(
        "job-1",
        worker_id="worker-a",
        now="2026-04-28T10:00:01Z",
        lease_expires_at="2026-04-28T10:05:01Z",
    )
    backend.claim_for_worker(
        "job-1",
        worker_id="worker-b",
        now="2026-04-28T10:05:02Z",
        lease_expires_at="2026-04-28T10:10:02Z",
    )

    assert backend.mark_terminal_for_worker(
        "job-1",
        worker_id="worker-a",
        status="succeeded",
        finished_at="2026-04-28T10:05:03Z",
        result={"report_markdown": "# Stale"},
        error=None,
    ) is None
    current = backend.get("job-1")
    assert current is not None
    assert current.status == "running"
```

- [ ] **Step 6: Implement ownership-aware terminal update**

Add this method inside `SQLiteResearchJobsBackend` before `mark_terminal()`:

```python
    def mark_terminal_for_worker(
        self,
        job_id: str,
        *,
        worker_id: str,
        status: str,
        finished_at: str,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> ResearchJob | None:
        if status not in TERMINAL_RESEARCH_JOB_STATUSES:
            raise ValueError(f"Invalid terminal status: {status}")
        result_json = json.dumps(result) if result is not None else None
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE research_jobs
                SET status = ?,
                    finished_at = ?,
                    result_json = ?,
                    error = ?,
                    worker_id = NULL,
                    lease_expires_at = NULL,
                    heartbeat_at = NULL
                WHERE id = ? AND worker_id = ? AND status = 'running'
                """,
                (status, finished_at, result_json, error, job_id, worker_id),
            )
            connection.commit()
        if cursor.rowcount != 1:
            return None
        self.prune_finished()
        return self.get(job_id)
```

- [ ] **Step 7: Run SQLite backend tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_research_jobs_sqlite_backend.py -v
```

Expected: all tests in `tests/test_research_jobs_sqlite_backend.py` pass.

- [ ] **Step 8: Commit backend helpers**

```powershell
git add src/insight_graph/research_jobs_sqlite_backend.py tests/test_research_jobs_sqlite_backend.py
git commit -m "feat: add sqlite research job leases"
```

## Task 3: Service Layer Lease Integration

**Files:**
- Modify: `tests/test_research_jobs.py`
- Modify: `src/insight_graph/research_jobs.py`

- [ ] **Step 1: Write failing service tests**

Append these tests to `tests/test_research_jobs.py`:

```python
def test_sqlite_mark_running_claims_job_with_worker_lease(tmp_path) -> None:
    jobs_module.configure_research_jobs_sqlite_backend(tmp_path / "jobs.sqlite3")
    try:
        created = jobs_module.create_research_job(
            query="Lease service",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )

        claimed = jobs_module.mark_research_job_running(
            created["job_id"],
            started_at=lambda: "2026-04-28T10:00:01Z",
            store_failure_finished_at=lambda: "2026-04-28T10:00:02Z",
            worker_id="worker-a",
            lease_expires_at=lambda started_at: "2026-04-28T10:05:01Z",
        )

        assert claimed is not None
        assert claimed.status == "running"
        assert claimed.started_at == "2026-04-28T10:00:01Z"
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()


def test_sqlite_heartbeat_research_job_returns_false_for_non_owner(tmp_path) -> None:
    jobs_module.configure_research_jobs_sqlite_backend(tmp_path / "jobs.sqlite3")
    try:
        created = jobs_module.create_research_job(
            query="Heartbeat service",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )
        assert jobs_module.mark_research_job_running(
            created["job_id"],
            started_at=lambda: "2026-04-28T10:00:01Z",
            store_failure_finished_at=lambda: "2026-04-28T10:00:02Z",
            worker_id="worker-a",
            lease_expires_at=lambda started_at: "2026-04-28T10:05:01Z",
        ) is not None

        assert jobs_module.heartbeat_research_job(
            created["job_id"],
            worker_id="worker-b",
            now="2026-04-28T10:01:01Z",
            lease_expires_at="2026-04-28T10:06:01Z",
        ) is False
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()


def test_sqlite_terminal_write_uses_worker_ownership(tmp_path) -> None:
    jobs_module.configure_research_jobs_sqlite_backend(tmp_path / "jobs.sqlite3")
    try:
        created = jobs_module.create_research_job(
            query="Terminal service",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )
        job = jobs_module.mark_research_job_running(
            created["job_id"],
            started_at=lambda: "2026-04-28T10:00:01Z",
            store_failure_finished_at=lambda: "2026-04-28T10:00:02Z",
            worker_id="worker-a",
            lease_expires_at=lambda started_at: "2026-04-28T10:05:01Z",
        )
        assert job is not None

        jobs_module.mark_research_job_succeeded(
            job,
            finished_at="2026-04-28T10:00:03Z",
            result={"report_markdown": "# Wrong"},
            worker_id="worker-b",
        )
        assert jobs_module.get_research_job_record(created["job_id"]).status == "running"

        jobs_module.mark_research_job_succeeded(
            job,
            finished_at="2026-04-28T10:00:04Z",
            result={"report_markdown": "# Right"},
            worker_id="worker-a",
        )
        assert jobs_module.get_research_job_record(created["job_id"]).status == "succeeded"
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_research_jobs.py::test_sqlite_mark_running_claims_job_with_worker_lease tests/test_research_jobs.py::test_sqlite_heartbeat_research_job_returns_false_for_non_owner tests/test_research_jobs.py::test_sqlite_terminal_write_uses_worker_ownership -v
```

Expected: FAIL because service helpers do not accept lease parameters yet.

- [ ] **Step 3: Add lease constants and process worker ID**

In `src/insight_graph/research_jobs.py`, add these constants after `_MAX_ACTIVE_RESEARCH_JOBS`:

```python
RESEARCH_JOB_LEASE_TTL_SECONDS = 300
RESEARCH_JOB_HEARTBEAT_INTERVAL_SECONDS = 60
_RESEARCH_JOBS_WORKER_ID = uuid4().hex
```

Add this helper after `_using_sqlite_research_jobs_backend()`:

```python
def research_jobs_worker_id() -> str:
    return _RESEARCH_JOBS_WORKER_ID


def using_sqlite_research_jobs_backend() -> bool:
    return _using_sqlite_research_jobs_backend()
```

- [ ] **Step 4: Make running transition SQLite-lease aware**

Change the `mark_research_job_running()` signature to:

```python
def mark_research_job_running(
    job_id: str,
    started_at: Callable[[], str],
    store_failure_finished_at: Callable[[], str],
    *,
    worker_id: str | None = None,
    lease_expires_at: Callable[[str], str] | None = None,
) -> ResearchJob | None:
```

Replace the SQLite branch with:

```python
        if _using_sqlite_research_jobs_backend():
            start_timestamp = started_at()
            lease_until = (
                lease_expires_at(start_timestamp)
                if lease_expires_at is not None
                else start_timestamp
            )
            try:
                return _RESEARCH_JOBS_BACKEND.claim_for_worker(
                    job_id,
                    worker_id=worker_id or _RESEARCH_JOBS_WORKER_ID,
                    now=start_timestamp,
                    lease_expires_at=lease_until,
                )
            except ValueError:
                return None
```

Leave the in-memory branch unchanged.

- [ ] **Step 5: Add service heartbeat helper**

Add this function after `mark_research_job_running()`:

```python
def heartbeat_research_job(
    job_id: str,
    *,
    worker_id: str,
    now: str,
    lease_expires_at: str,
) -> bool:
    with _JOBS_LOCK:
        if not _using_sqlite_research_jobs_backend():
            return False
        return _RESEARCH_JOBS_BACKEND.heartbeat(
            job_id,
            worker_id=worker_id,
            now=now,
            lease_expires_at=lease_expires_at,
        )
```

- [ ] **Step 6: Make terminal helpers ownership-aware for SQLite**

Change `mark_research_job_failed()` signature to include an optional keyword-only worker ID:

```python
def mark_research_job_failed(
    job: ResearchJob,
    finished_at: str,
    error: str,
    *,
    worker_id: str | None = None,
) -> None:
```

In its SQLite branch, call `mark_terminal_for_worker()` when `worker_id` is provided:

```python
        if _using_sqlite_research_jobs_backend():
            if worker_id is not None:
                _RESEARCH_JOBS_BACKEND.mark_terminal_for_worker(
                    job.id,
                    worker_id=worker_id,
                    status=RESEARCH_JOB_STATUS_FAILED,
                    finished_at=finished_at,
                    result=None,
                    error=error,
                )
                return
            _RESEARCH_JOBS_BACKEND.mark_terminal(
                job.id,
                status=RESEARCH_JOB_STATUS_FAILED,
                finished_at=finished_at,
                result=None,
                error=error,
            )
            return
```

Change `mark_research_job_succeeded()` signature to include an optional keyword-only worker ID:

```python
def mark_research_job_succeeded(
    job: ResearchJob,
    finished_at: str,
    result: dict[str, Any],
    *,
    worker_id: str | None = None,
) -> None:
```

In its SQLite branch, call `mark_terminal_for_worker()` when `worker_id` is provided:

```python
        if _using_sqlite_research_jobs_backend():
            if worker_id is not None:
                _RESEARCH_JOBS_BACKEND.mark_terminal_for_worker(
                    job.id,
                    worker_id=worker_id,
                    status=RESEARCH_JOB_STATUS_SUCCEEDED,
                    finished_at=finished_at,
                    result=result,
                    error=None,
                )
                return
            _RESEARCH_JOBS_BACKEND.mark_terminal(
                job.id,
                status=RESEARCH_JOB_STATUS_SUCCEEDED,
                finished_at=finished_at,
                result=result,
                error=None,
            )
            return
```

- [ ] **Step 7: Run service tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_research_jobs.py::test_sqlite_mark_running_claims_job_with_worker_lease tests/test_research_jobs.py::test_sqlite_heartbeat_research_job_returns_false_for_non_owner tests/test_research_jobs.py::test_sqlite_terminal_write_uses_worker_ownership -v
```

Expected: PASS.

- [ ] **Step 8: Run existing repository contract tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_research_jobs.py -v
```

Expected: all tests in `tests/test_research_jobs.py` pass for both memory and SQLite fixtures.

- [ ] **Step 9: Commit service integration**

```powershell
git add src/insight_graph/research_jobs.py tests/test_research_jobs.py
git commit -m "feat: route sqlite jobs through leases"
```

## Task 4: API Heartbeat Loop

**Files:**
- Modify: `tests/test_api.py`
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Write failing API smoke test**

Append this test to `tests/test_api.py`:

```python
def test_sqlite_research_job_execution_hides_lease_metadata(monkeypatch, tmp_path) -> None:
    clear_live_env(monkeypatch)
    jobs_module.configure_research_jobs_sqlite_backend(tmp_path / "jobs.sqlite3")
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(
        api_module,
        "run_research",
        lambda query: make_api_state(query),
    )

    try:
        client = TestClient(api_module.app)
        response = client.post(
            "/research/jobs",
            json={"query": "SQLite lease smoke", "preset": "offline"},
        )
        assert response.status_code == 202
        detail_response = client.get(f"/research/jobs/{response.json()['job_id']}")
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "succeeded"
    assert "worker_id" not in detail
    assert "lease_expires_at" not in detail
    assert "heartbeat_at" not in detail
    assert "attempt_count" not in detail
```

- [ ] **Step 2: Run test to verify current behavior fails after lease-only service change**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py::test_sqlite_research_job_execution_hides_lease_metadata -v
```

Expected before API integration: FAIL or hang-free incomplete execution if `_run_research_job()` does not pass worker ownership consistently.

- [ ] **Step 3: Add API imports**

In `src/insight_graph/api.py`, add imports:

```python
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
```

Extend the `insight_graph.research_jobs` import list with:

```python
    RESEARCH_JOB_HEARTBEAT_INTERVAL_SECONDS,
    RESEARCH_JOB_LEASE_TTL_SECONDS,
    heartbeat_research_job,
    research_jobs_worker_id,
    using_sqlite_research_jobs_backend,
```

- [ ] **Step 4: Add lease timestamp and heartbeat helpers**

Add these helpers near `_current_utc_timestamp()`:

```python
def _add_seconds_to_timestamp(timestamp: str, seconds: int) -> str:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return (parsed + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _lease_expires_at(started_at: str) -> str:
    return _add_seconds_to_timestamp(started_at, RESEARCH_JOB_LEASE_TTL_SECONDS)


def _start_research_job_heartbeat(job_id: str, worker_id: str) -> tuple[Event, Thread | None]:
    stop_event = Event()
    if not using_sqlite_research_jobs_backend():
        return stop_event, None

    def heartbeat_loop() -> None:
        while not stop_event.wait(RESEARCH_JOB_HEARTBEAT_INTERVAL_SECONDS):
            now = _current_utc_timestamp()
            heartbeat_research_job(
                job_id,
                worker_id=worker_id,
                now=now,
                lease_expires_at=_lease_expires_at(now),
            )

    thread = Thread(target=heartbeat_loop, name=f"research-job-heartbeat-{job_id}", daemon=True)
    thread.start()
    return stop_event, thread


def _stop_research_job_heartbeat(stop_event: Event, thread: Thread | None) -> None:
    stop_event.set()
    if thread is not None:
        thread.join(timeout=1)
```

- [ ] **Step 5: Pass worker ownership through `_run_research_job()`**

Replace `_run_research_job()` with this shape:

```python
def _run_research_job(job_id: str) -> None:
    worker_id = research_jobs_worker_id()
    job = mark_research_job_running(
        job_id=job_id,
        started_at=_current_utc_timestamp,
        store_failure_finished_at=_current_utc_timestamp,
        worker_id=worker_id,
        lease_expires_at=_lease_expires_at,
    )
    if job is None:
        return

    stop_event, heartbeat_thread = _start_research_job_heartbeat(job.id, worker_id)
    try:
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
                worker_id=worker_id,
            )
            return

        mark_research_job_succeeded(
            job,
            finished_at=_current_utc_timestamp(),
            result=result,
            worker_id=worker_id,
        )
    finally:
        _stop_research_job_heartbeat(stop_event, heartbeat_thread)
```

- [ ] **Step 6: Run API smoke test**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py::test_sqlite_research_job_execution_hides_lease_metadata -v
```

Expected: PASS.

- [ ] **Step 7: Run API test file**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py -v
```

Expected: all API tests pass.

- [ ] **Step 8: Commit API integration**

```powershell
git add src/insight_graph/api.py tests/test_api.py
git commit -m "feat: heartbeat sqlite research job leases"
```

## Task 5: Docs and Regression Verification

**Files:**
- Modify: `docs/research-job-repository-contract.md`
- Modify: `docs/roadmap.md`

- [ ] **Step 1: Update repository contract docs**

Add this section to `docs/research-job-repository-contract.md` near backend responsibilities:

```markdown
## SQLite worker leasing

When the SQLite backend is selected, background execution uses internal worker leases.

- Workers claim queued jobs before running workflows.
- Claiming sets internal lease metadata and moves the job to `running`.
- Expired `running` jobs are requeued on later claim attempts.
- Heartbeats extend leases while workflows run.
- Terminal writes are accepted only from the worker that owns the lease.
- Lease metadata is internal and is not exposed by API responses.

The in-memory backend keeps its existing single-process behavior and does not simulate leases.
```

- [ ] **Step 2: Update roadmap**

In `docs/roadmap.md`, replace the deferred work line:

```markdown
- Add multi-process job coordination only after storage abstraction exists.
```

with:

```markdown
- Done: SQLite worker leasing coordinates multi-process job execution and requeues expired running jobs.
```

- [ ] **Step 3: Run focused test suite**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_research_jobs_sqlite_backend.py tests/test_research_jobs.py tests/test_api.py -v
```

Expected: all focused tests pass.

- [ ] **Step 4: Run lint**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
```

Expected: `All checks passed!`.

- [ ] **Step 5: Run full test suite**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
```

Expected: full suite passes with the existing skipped test count.

- [ ] **Step 6: Run whitespace diff check**

Run:

```powershell
git diff --check
```

Expected: no output.

- [ ] **Step 7: Commit docs and verification cleanup**

```powershell
git add docs/research-job-repository-contract.md docs/roadmap.md
git commit -m "docs: document sqlite research job leasing"
```

## Self-Review Checklist

- Spec coverage: schema columns, migration, SQLite-only scope, claim, heartbeat, reclaim, terminal ownership, API compatibility, tests, docs, and constants are covered by tasks.
- Placeholder scan: this plan contains no unfinished markers and no unspecified implementation steps.
- Type consistency: planned backend names are `claim_for_worker()`, `heartbeat()`, and `mark_terminal_for_worker()`; service names are `heartbeat_research_job()`, `research_jobs_worker_id()`, and `using_sqlite_research_jobs_backend()`.
- Scope check: the plan is one subsystem, SQLite worker leasing, and does not add public lease fields or in-memory lease simulation.
