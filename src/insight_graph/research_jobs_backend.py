from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, fields, replace
from pathlib import Path
from threading import RLock
from typing import Any

ACTIVE_RESEARCH_JOB_STATUSES = {"queued", "running"}
TERMINAL_RESEARCH_JOB_STATUSES = {"succeeded", "failed", "cancelled"}


@dataclass(frozen=True)
class ResearchJobsBackendSnapshot:
    next_job_sequence: int
    jobs: dict[str, Any]


class InMemoryResearchJobsBackend:
    def __init__(
        self,
        *,
        store_path: Path | None,
        jobs: dict[str, Any] | None = None,
        lock: Any | None = None,
    ) -> None:
        self._lock = lock if lock is not None else RLock()
        self._max_research_jobs = 100
        self._max_active_research_jobs = 100
        self._next_job_sequence = 0
        self._jobs: dict[str, Any] = jobs if jobs is not None else {}
        self._store_path = store_path

    def reset(
        self,
        *,
        next_job_sequence: int = 0,
        store_path: Path | None = None,
        retained_limit: int = 100,
        active_limit: int = 100,
        jobs: Iterable[Any] = (),
    ) -> None:
        with self._lock:
            self._next_job_sequence = next_job_sequence
            self._store_path = store_path
            self._max_research_jobs = retained_limit
            self._max_active_research_jobs = active_limit
            self._jobs.clear()
            self._jobs.update((job.id, replace(job)) for job in jobs)

    def seed(self, jobs: Iterable[Any], *, next_job_sequence: int | None = None) -> None:
        with self._lock:
            if next_job_sequence is not None:
                self._next_job_sequence = next_job_sequence
            self._jobs.update((job.id, replace(job)) for job in jobs)

    def set_store_path(self, path: Path | None) -> None:
        with self._lock:
            self._store_path = path

    def set_limits(self, *, retained_limit: int = 100, active_limit: int = 100) -> None:
        with self._lock:
            self._max_research_jobs = retained_limit
            self._max_active_research_jobs = active_limit

    def set_next_sequence(self, value: int) -> None:
        with self._lock:
            self._next_job_sequence = value

    def get(self, job_id: str) -> Any | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return replace(job)

    def all_jobs(self) -> list[Any]:
        with self._lock:
            return [replace(job) for job in self._jobs.values()]

    def update(self, job_id: str, **changes: Any) -> Any | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            valid_fields = {field.name for field in fields(job)}
            for name, value in changes.items():
                if name not in valid_fields:
                    raise ValueError(f"Unknown research job field: {name}")
                setattr(job, name, value)
            return replace(job)

    def next_sequence(self) -> int:
        with self._lock:
            return self._next_job_sequence

    def retained_limit(self) -> int:
        with self._lock:
            return self._max_research_jobs

    def active_limit(self) -> int:
        with self._lock:
            return self._max_active_research_jobs

    def active_count(self) -> int:
        with self._lock:
            return sum(
                1 for job in self._jobs.values() if job.status in ACTIVE_RESEARCH_JOB_STATUSES
            )

    def prune_finished(self) -> None:
        with self._lock:
            finished_jobs = [
                job
                for job in self._jobs.values()
                if job.status in TERMINAL_RESEARCH_JOB_STATUSES
            ]
            overflow = len(finished_jobs) - self._max_research_jobs
            if overflow <= 0:
                return

            for job in sorted(finished_jobs, key=lambda item: item.created_order)[:overflow]:
                del self._jobs[job.id]

    def delete_terminal_before(self, finished_before: str) -> int:
        with self._lock:
            expired_ids = [
                job.id
                for job in self._jobs.values()
                if job.status in TERMINAL_RESEARCH_JOB_STATUSES
                and job.finished_at is not None
                and job.finished_at < finished_before
            ]
            for job_id in expired_ids:
                del self._jobs[job_id]
            return len(expired_ids)

    def snapshot(self) -> ResearchJobsBackendSnapshot:
        with self._lock:
            return ResearchJobsBackendSnapshot(
                next_job_sequence=self._next_job_sequence,
                jobs=dict(self._jobs),
            )

    def restore(self, snapshot: ResearchJobsBackendSnapshot) -> None:
        with self._lock:
            self._next_job_sequence = snapshot.next_job_sequence
            self._jobs.clear()
            self._jobs.update(snapshot.jobs)
