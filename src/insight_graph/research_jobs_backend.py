from __future__ import annotations

from collections.abc import Iterable
from dataclasses import fields, replace
from pathlib import Path
from threading import Lock
from typing import Any


class InMemoryResearchJobsBackend:
    def __init__(
        self,
        *,
        store_path: Path | None,
        jobs: dict[str, Any] | None = None,
        lock: Lock | None = None,
    ) -> None:
        self._lock = lock if lock is not None else Lock()
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
