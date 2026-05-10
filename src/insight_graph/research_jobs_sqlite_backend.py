from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

from insight_graph.cli import ResearchPreset
from insight_graph.report_quality.intensity import ReportIntensity
from insight_graph.research_jobs import ResearchJob
from insight_graph.research_jobs_backend import (
    ACTIVE_RESEARCH_JOB_STATUSES,
    TERMINAL_RESEARCH_JOB_STATUSES,
    ResearchJobsBackendSnapshot,
)
from insight_graph.research_jobs_store import load_research_jobs

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_jobs (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    preset TEXT NOT NULL,
    report_intensity TEXT NOT NULL DEFAULT 'standard',
    single_entity_detail_mode TEXT NOT NULL DEFAULT 'auto',
    relevance_judge TEXT NOT NULL DEFAULT 'deterministic',
    fetch_rendered TEXT NOT NULL DEFAULT 'auto',
    search_provider TEXT NOT NULL DEFAULT 'auto',
    web_search_mode TEXT NOT NULL DEFAULT 'auto',
    status TEXT NOT NULL CHECK (
        status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')
    ),
    created_order INTEGER NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    result_json TEXT,
    error TEXT,
    events_json TEXT,
    worker_id TEXT,
    lease_expires_at TEXT,
    heartbeat_at TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0
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


def job_to_row(job: ResearchJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "query": job.query,
        "preset": job.preset.value,
        "report_intensity": job.report_intensity.value,
        "single_entity_detail_mode": job.single_entity_detail_mode,
        "relevance_judge": job.relevance_judge,
        "fetch_rendered": job.fetch_rendered,
        "search_provider": job.search_provider,
        "web_search_mode": job.web_search_mode,
        "status": job.status,
        "created_order": job.created_order,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result_json": json.dumps(job.result) if job.result is not None else None,
        "error": job.error,
        "events_json": json.dumps(job.events),
        "worker_id": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
        "attempt_count": 0,
    }


def job_from_row(row: sqlite3.Row) -> ResearchJob:
    result_json = row["result_json"]
    return ResearchJob(
        id=row["id"],
        query=row["query"],
        preset=ResearchPreset(row["preset"]),
        report_intensity=ReportIntensity(row["report_intensity"]),
        single_entity_detail_mode=row["single_entity_detail_mode"] or "auto",
        relevance_judge=row["relevance_judge"] if "relevance_judge" in row.keys() else "deterministic",
        fetch_rendered=row["fetch_rendered"] if "fetch_rendered" in row.keys() else "auto",
        search_provider=row["search_provider"] or "auto",
        web_search_mode=row["web_search_mode"] or "auto",
        created_order=row["created_order"],
        created_at=row["created_at"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        result=json.loads(result_json) if result_json is not None else None,
        error=row["error"],
        events=json.loads(row["events_json"]) if row["events_json"] is not None else [],
    )


def ensure_lease_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(research_jobs)")
    }
    migrations = {
        "events_json": "ALTER TABLE research_jobs ADD COLUMN events_json TEXT",
        "report_intensity": (
            "ALTER TABLE research_jobs "
            "ADD COLUMN report_intensity TEXT NOT NULL DEFAULT 'standard'"
        ),
        "single_entity_detail_mode": (
            "ALTER TABLE research_jobs "
            "ADD COLUMN single_entity_detail_mode TEXT NOT NULL DEFAULT 'auto'"
        ),
        "relevance_judge": (
            "ALTER TABLE research_jobs "
            "ADD COLUMN relevance_judge TEXT NOT NULL DEFAULT 'deterministic'"
        ),
        "fetch_rendered": (
            "ALTER TABLE research_jobs "
            "ADD COLUMN fetch_rendered TEXT NOT NULL DEFAULT 'auto'"
        ),
        "search_provider": (
            "ALTER TABLE research_jobs "
            "ADD COLUMN search_provider TEXT NOT NULL DEFAULT 'auto'"
        ),
        "web_search_mode": (
            "ALTER TABLE research_jobs "
            "ADD COLUMN web_search_mode TEXT NOT NULL DEFAULT 'auto'"
        ),
        "worker_id": "ALTER TABLE research_jobs ADD COLUMN worker_id TEXT",
        "lease_expires_at": "ALTER TABLE research_jobs ADD COLUMN lease_expires_at TEXT",
        "heartbeat_at": "ALTER TABLE research_jobs ADD COLUMN heartbeat_at TEXT",
        "attempt_count": (
            "ALTER TABLE research_jobs "
            "ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"
        ),
    }
    for column_name, statement in migrations.items():
        if column_name not in existing_columns:
            connection.execute(statement)


class SQLiteResearchJobsBackend:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._store_path: Path | None = None
        self._max_research_jobs = 100
        self._max_active_research_jobs = 100

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
            ensure_lease_columns(connection)
            connection.execute(
                """
                INSERT OR IGNORE INTO research_job_meta (key, value)
                VALUES ('next_sequence', 0)
                """
            )
            connection.commit()

    def reset(
        self,
        *,
        next_job_sequence: int = 0,
        store_path: Path | None = None,
        retained_limit: int = 100,
        active_limit: int = 100,
        jobs: Iterable[ResearchJob] = (),
    ) -> None:
        self.initialize()
        self._store_path = store_path
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
                    id, query, preset, report_intensity, single_entity_detail_mode,
                    relevance_judge, search_provider, web_search_mode,
                    status, created_order, created_at,
                    started_at, finished_at, result_json, error,
                    events_json, worker_id, lease_expires_at, heartbeat_at, attempt_count
                ) VALUES (
                    :id, :query, :preset, :report_intensity, :single_entity_detail_mode,
                    :relevance_judge, :search_provider, :web_search_mode,
                    :status, :created_order, :created_at,
                    :started_at, :finished_at, :result_json, :error,
                    :events_json, :worker_id, :lease_expires_at, :heartbeat_at, :attempt_count
                )
                """,
                [job_to_row(job) for job in jobs],
            )
            connection.commit()

    def seed(
        self,
        jobs: Iterable[ResearchJob],
        *,
        next_job_sequence: int | None = None,
    ) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if next_job_sequence is not None:
                connection.execute(
                    "UPDATE research_job_meta SET value = ? WHERE key = 'next_sequence'",
                    (next_job_sequence,),
                )
            connection.executemany(
                """
                INSERT OR REPLACE INTO research_jobs (
                    id, query, preset, report_intensity, single_entity_detail_mode,
                    relevance_judge, search_provider, web_search_mode,
                    status, created_order, created_at,
                    started_at, finished_at, result_json, error,
                    events_json, worker_id, lease_expires_at, heartbeat_at, attempt_count
                ) VALUES (
                    :id, :query, :preset, :report_intensity, :single_entity_detail_mode,
                    :search_provider, :web_search_mode,
                    :status, :created_order, :created_at,
                    :started_at, :finished_at, :result_json, :error,
                    :events_json, :worker_id, :lease_expires_at, :heartbeat_at, :attempt_count
                )
                """,
                [job_to_row(job) for job in jobs],
            )
            connection.commit()

    def set_store_path(self, path: Path | None) -> None:
        self._store_path = path

    def set_limits(self, *, retained_limit: int = 100, active_limit: int = 100) -> None:
        self._max_research_jobs = retained_limit
        self._max_active_research_jobs = active_limit

    def set_next_sequence(self, value: int) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE research_job_meta SET value = ? WHERE key = 'next_sequence'",
                (value,),
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

    def all_jobs(self) -> list[ResearchJob]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM research_jobs ORDER BY created_order DESC"
            ).fetchall()
        return [job_from_row(row) for row in rows]

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
                    report_intensity = :report_intensity,
                    single_entity_detail_mode = :single_entity_detail_mode,
                    status = :status,
                    created_order = :created_order,
                    created_at = :created_at,
                    started_at = :started_at,
                    finished_at = :finished_at,
                    result_json = :result_json,
                    error = :error,
                    events_json = :events_json
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

    def delete_terminal_before(self, finished_before: str) -> int:
        placeholders = ",".join("?" for _ in TERMINAL_RESEARCH_JOB_STATUSES)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                f"""
                DELETE FROM research_jobs
                WHERE status IN ({placeholders})
                  AND finished_at IS NOT NULL
                  AND finished_at < ?
                """,
                (*tuple(TERMINAL_RESEARCH_JOB_STATUSES), finished_before),
            )
            connection.commit()
        return cursor.rowcount

    def delete_job(self, job_id: str) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "DELETE FROM research_jobs WHERE id = ?",
                (job_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

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

    def create_job(
        self,
        *,
        job_id: str,
        query: str,
        preset: ResearchPreset,
        report_intensity: ReportIntensity = ReportIntensity.standard,
        single_entity_detail_mode: str = "auto",
        relevance_judge: str = "deterministic",
        fetch_rendered: str = "auto",
        search_provider: str = "auto",
        web_search_mode: str = "auto",
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
            next_sequence = (
                connection.execute(
                    "SELECT value FROM research_job_meta WHERE key = 'next_sequence'"
                ).fetchone()["value"]
                + 1
            )
            connection.execute(
                "UPDATE research_job_meta SET value = ? WHERE key = 'next_sequence'",
                (next_sequence,),
            )
            job = ResearchJob(
                id=job_id,
                query=query,
                preset=preset,
                report_intensity=report_intensity,
                single_entity_detail_mode=single_entity_detail_mode,
                relevance_judge=relevance_judge,
                fetch_rendered=fetch_rendered,
                search_provider=search_provider,
                web_search_mode=web_search_mode,
                created_order=next_sequence,
                created_at=created_at,
            )
            connection.execute(
                """
                INSERT INTO research_jobs (
                    id, query, preset, report_intensity, single_entity_detail_mode,
                    relevance_judge, fetch_rendered, search_provider, web_search_mode,
                    status, created_order, created_at,
                    started_at, finished_at, result_json, error,
                    events_json, worker_id, lease_expires_at, heartbeat_at, attempt_count
                ) VALUES (
                    :id, :query, :preset, :report_intensity, :single_entity_detail_mode,
                    :relevance_judge, :fetch_rendered, :search_provider, :web_search_mode,
                    :status, :created_order, :created_at,
                    :started_at, :finished_at, :result_json, :error,
                    :events_json, :worker_id, :lease_expires_at, :heartbeat_at, :attempt_count
                )
                """,
                job_to_row(job),
            )
            connection.commit()
        self.prune_finished()
        return job

    def cancel_queued(self, job_id: str, *, finished_at: str) -> ResearchJob | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM research_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if current is None:
                connection.rollback()
                return None
            if current["status"] not in ("queued", "running"):
                connection.rollback()
                raise ValueError("Only queued or running research jobs can be cancelled")
            connection.execute(
                """
                UPDATE research_jobs
                SET status = 'cancelled', finished_at = ?
                WHERE id = ? AND status IN ('queued', 'running')
                """,
                (finished_at, job_id),
            )
            connection.commit()
        return self.get(job_id)

    def is_cancelled(self, job_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM research_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            return row is not None and row["status"] == "cancelled"

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

    def claim_next_for_worker(
        self,
        *,
        worker_id: str,
        now: str,
        lease_expires_at: str,
    ) -> ResearchJob | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._requeue_expired_running(connection, now=now)
            current = connection.execute(
                """
                SELECT * FROM research_jobs
                WHERE status = 'queued'
                ORDER BY created_order ASC
                LIMIT 1
                """
            ).fetchone()
            if current is None:
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
                (started_at, worker_id, now, lease_expires_at, current["id"]),
            )
            connection.commit()
        return self.get(str(current["id"]))

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

    def mark_running(self, job_id: str, *, started_at: str) -> ResearchJob | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM research_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if current is None or current["status"] == "cancelled":
                connection.rollback()
                return None
            if current["status"] != "queued":
                connection.rollback()
                raise ValueError("Only queued research jobs can start running")
            connection.execute(
                """
                UPDATE research_jobs
                SET status = 'running', started_at = ?
                WHERE id = ? AND status = 'queued'
                """,
                (started_at, job_id),
            )
            connection.commit()
        return self.get(job_id)

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

    def import_json_store(self, path: Path, *, restart_timestamp: str) -> None:
        loaded = load_research_jobs(path=path, restart_timestamp=restart_timestamp)
        jobs = [
            ResearchJob(
                id=item["id"],
                query=item["query"],
                preset=ResearchPreset(item["preset"]),
                report_intensity=ReportIntensity(item.get("report_intensity", "standard")),
                single_entity_detail_mode=item.get("single_entity_detail_mode", "auto"),
                search_provider=item.get("search_provider", "auto"),
                web_search_mode=item.get("web_search_mode", "auto"),
                created_order=item["created_order"],
                created_at=item["created_at"],
                status=item["status"],
                started_at=item["started_at"],
                finished_at=item["finished_at"],
                result=item["result"],
                error=item["error"],
                events=item.get("events") or [],
            )
            for item in loaded.jobs
        ]
        self.reset(next_job_sequence=loaded.next_job_sequence, jobs=jobs)
