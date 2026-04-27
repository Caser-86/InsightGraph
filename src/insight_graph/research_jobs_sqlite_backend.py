from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

from insight_graph.cli import ResearchPreset
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
    status TEXT NOT NULL CHECK (
        status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')
    ),
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
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM research_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if current is None:
                connection.rollback()
                return None
            if current["status"] != "queued":
                connection.rollback()
                raise ValueError("Only queued research jobs can be cancelled")
            connection.execute(
                """
                UPDATE research_jobs
                SET status = 'cancelled', finished_at = ?
                WHERE id = ? AND status = 'queued'
                """,
                (finished_at, job_id),
            )
            connection.commit()
        return self.get(job_id)

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
