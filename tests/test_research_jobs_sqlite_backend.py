import json
import sqlite3

import pytest

from insight_graph.cli import ResearchPreset
from insight_graph.research_jobs import ResearchJob
from insight_graph.research_jobs_sqlite_backend import (
    SQLiteResearchJobsBackend,
    job_from_row,
    job_to_row,
)


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


def test_sqlite_backend_initializes_events_column(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"

    backend = SQLiteResearchJobsBackend(db_path)
    backend.initialize()

    assert "events_json" in sqlite_columns(db_path, "research_jobs")


def test_sqlite_backend_migrates_existing_database_with_missing_lease_columns(
    tmp_path,
) -> None:
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
    assert "events_json" in sqlite_columns(db_path, "research_jobs")


def test_sqlite_backend_persists_job_events(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    backend = SQLiteResearchJobsBackend(db_path)
    backend.initialize()
    job = ResearchJob(
        id="job-1",
        query="Events",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        events=[{"type": "stage_started", "stage": "planner", "sequence": 1}],
    )

    backend.reset(jobs=[job], next_job_sequence=1)

    stored = backend.get("job-1")
    assert stored is not None
    assert stored.events == [
        {"type": "stage_started", "stage": "planner", "sequence": 1}
    ]
    row = sqlite_job_row(db_path, "job-1")
    assert json.loads(row["events_json"]) == stored.events


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
    assert (
        backend.claim_for_worker(
            "job-1",
            worker_id="worker-a",
            now="2026-04-28T10:00:01Z",
            lease_expires_at="2026-04-28T10:05:01Z",
        )
        is not None
    )

    assert (
        backend.claim_for_worker(
            "job-1",
            worker_id="worker-b",
            now="2026-04-28T10:01:00Z",
            lease_expires_at="2026-04-28T10:06:00Z",
        )
        is None
    )


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

    assert (
        backend.heartbeat(
            "job-1",
            worker_id="worker-a",
            now="2026-04-28T10:01:01Z",
            lease_expires_at="2026-04-28T10:06:01Z",
        )
        is True
    )
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

    assert (
        backend.heartbeat(
            "job-1",
            worker_id="worker-b",
            now="2026-04-28T10:01:01Z",
            lease_expires_at="2026-04-28T10:06:01Z",
        )
        is False
    )
    row = sqlite_job_row(db_path, "job-1")
    assert row["worker_id"] == "worker-a"
    assert row["heartbeat_at"] == "2026-04-28T10:00:01Z"


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

    assert (
        backend.mark_terminal_for_worker(
            "job-1",
            worker_id="worker-b",
            status="succeeded",
            finished_at="2026-04-28T10:00:03Z",
            result={"report_markdown": "# Wrong"},
            error=None,
        )
        is None
    )

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

    assert (
        backend.mark_terminal_for_worker(
            "job-1",
            worker_id="worker-a",
            status="succeeded",
            finished_at="2026-04-28T10:05:03Z",
            result={"report_markdown": "# Stale"},
            error=None,
        )
        is None
    )
    current = backend.get("job-1")
    assert current is not None
    assert current.status == "running"


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

    updated = backend.update(
        "job-1",
        status="running",
        started_at="2026-04-28T10:00:01Z",
    )
    assert updated is not None
    assert updated.status == "running"
    assert backend.next_sequence() == 1
    assert backend.retained_limit() == 3
    assert backend.active_limit() == 2


def test_sqlite_backend_counts_active_jobs_and_prunes_terminal_jobs(tmp_path) -> None:
    backend = SQLiteResearchJobsBackend(tmp_path / "jobs.sqlite3")
    backend.initialize()
    backend.reset(
        retained_limit=1,
        jobs=[
            ResearchJob(
                id="old",
                query="Old",
                preset=ResearchPreset.offline,
                created_order=1,
                created_at="2026-04-28T10:00:00Z",
                status="succeeded",
            ),
            ResearchJob(
                id="queued",
                query="Queued",
                preset=ResearchPreset.offline,
                created_order=2,
                created_at="2026-04-28T10:00:01Z",
            ),
            ResearchJob(
                id="running",
                query="Running",
                preset=ResearchPreset.offline,
                created_order=3,
                created_at="2026-04-28T10:00:02Z",
                status="running",
            ),
            ResearchJob(
                id="new",
                query="New",
                preset=ResearchPreset.offline,
                created_order=4,
                created_at="2026-04-28T10:00:03Z",
                status="failed",
            ),
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
    backend.reset(
        jobs=[
            ResearchJob(
                id="job-1",
                query="Queued",
                preset=ResearchPreset.offline,
                created_order=1,
                created_at="2026-04-28T10:00:00Z",
            )
        ]
    )

    cancelled = backend.cancel_queued("job-1", finished_at="2026-04-28T10:00:01Z")
    assert cancelled is not None
    assert cancelled.status == "cancelled"

    assert backend.mark_running("job-1", started_at="2026-04-28T10:00:02Z") is None


def test_sqlite_backend_terminal_update_is_best_effort_compatible(tmp_path) -> None:
    backend = SQLiteResearchJobsBackend(tmp_path / "jobs.sqlite3")
    backend.initialize()
    job = ResearchJob(
        id="job-1",
        query="Running",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="running",
    )
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
