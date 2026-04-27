from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException

from insight_graph.cli import ResearchPreset
from insight_graph.research_jobs_backend import InMemoryResearchJobsBackend
from insight_graph.research_jobs_store import (
    ResearchJobsStoreError,
    load_research_jobs,
    research_jobs_backend_from_env,
    research_jobs_path_from_env,
    research_jobs_sqlite_path_from_env,
    save_research_jobs,
)

RESEARCH_JOB_STATUS_QUEUED = "queued"
RESEARCH_JOB_STATUS_RUNNING = "running"
RESEARCH_JOB_STATUS_SUCCEEDED = "succeeded"
RESEARCH_JOB_STATUS_FAILED = "failed"
RESEARCH_JOB_STATUS_CANCELLED = "cancelled"
RESEARCH_JOB_STATUSES = (
    RESEARCH_JOB_STATUS_QUEUED,
    RESEARCH_JOB_STATUS_RUNNING,
    RESEARCH_JOB_STATUS_SUCCEEDED,
    RESEARCH_JOB_STATUS_FAILED,
    RESEARCH_JOB_STATUS_CANCELLED,
)
ResearchJobStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
]
ACTIVE_RESEARCH_JOB_STATUSES = {
    RESEARCH_JOB_STATUS_QUEUED,
    RESEARCH_JOB_STATUS_RUNNING,
}
TERMINAL_RESEARCH_JOB_STATUSES = {
    RESEARCH_JOB_STATUS_SUCCEEDED,
    RESEARCH_JOB_STATUS_FAILED,
    RESEARCH_JOB_STATUS_CANCELLED,
}
RETRYABLE_RESEARCH_JOB_STATUSES = {
    RESEARCH_JOB_STATUS_FAILED,
    RESEARCH_JOB_STATUS_CANCELLED,
}
_JOBS_LOCK = RLock()
_MAX_RESEARCH_JOBS = 100
_MAX_ACTIVE_RESEARCH_JOBS = 100
_NEXT_JOB_SEQUENCE = 0
_JOBS: dict[str, "ResearchJob"] = {}
_RESEARCH_JOBS_PATH: Path | None = research_jobs_path_from_env()
_RESEARCH_JOBS_BACKEND = InMemoryResearchJobsBackend(
    store_path=_RESEARCH_JOBS_PATH,
    jobs=_JOBS,
    lock=_JOBS_LOCK,
)


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


def reset_research_jobs_state(
    *,
    next_job_sequence: int = 0,
    store_path: Path | None = None,
    retained_limit: int = 100,
    active_limit: int = 100,
    jobs: Iterable[ResearchJob] = (),
) -> None:
    global _MAX_ACTIVE_RESEARCH_JOBS, _MAX_RESEARCH_JOBS, _NEXT_JOB_SEQUENCE, _RESEARCH_JOBS_PATH

    jobs = tuple(jobs)
    _RESEARCH_JOBS_BACKEND.reset(
        next_job_sequence=next_job_sequence,
        store_path=store_path,
        retained_limit=retained_limit,
        active_limit=active_limit,
        jobs=jobs,
    )
    with _JOBS_LOCK:
        _NEXT_JOB_SEQUENCE = next_job_sequence
        _RESEARCH_JOBS_PATH = store_path
        _MAX_RESEARCH_JOBS = retained_limit
        _MAX_ACTIVE_RESEARCH_JOBS = active_limit
        _JOBS.clear()
        _JOBS.update((job.id, replace(job)) for job in jobs)


def seed_research_job(job: ResearchJob, *, next_job_sequence: int | None = None) -> None:
    seed_research_jobs([job], next_job_sequence=next_job_sequence)


def seed_research_jobs(
    jobs: Iterable[ResearchJob],
    *,
    next_job_sequence: int | None = None,
) -> None:
    global _NEXT_JOB_SEQUENCE

    jobs = tuple(jobs)
    _RESEARCH_JOBS_BACKEND.seed(jobs, next_job_sequence=next_job_sequence)
    with _JOBS_LOCK:
        if next_job_sequence is not None:
            _NEXT_JOB_SEQUENCE = next_job_sequence
        _JOBS.update((job.id, replace(job)) for job in jobs)


def set_research_jobs_store_path(path: Path | None) -> None:
    global _RESEARCH_JOBS_PATH

    _RESEARCH_JOBS_BACKEND.set_store_path(path)
    with _JOBS_LOCK:
        _RESEARCH_JOBS_PATH = path


def set_research_job_limits(*, retained_limit: int = 100, active_limit: int = 100) -> None:
    global _MAX_ACTIVE_RESEARCH_JOBS, _MAX_RESEARCH_JOBS

    _RESEARCH_JOBS_BACKEND.set_limits(
        retained_limit=retained_limit,
        active_limit=active_limit,
    )
    with _JOBS_LOCK:
        _MAX_RESEARCH_JOBS = retained_limit
        _MAX_ACTIVE_RESEARCH_JOBS = active_limit


def get_research_job_record(job_id: str) -> ResearchJob | None:
    return _RESEARCH_JOBS_BACKEND.get(job_id)


def update_research_job_record(job_id: str, **changes: Any) -> ResearchJob | None:
    return _RESEARCH_JOBS_BACKEND.update(job_id, **changes)


def get_next_research_job_sequence() -> int:
    with _JOBS_LOCK:
        return _NEXT_JOB_SEQUENCE


def _make_research_jobs_backend_from_env() -> Any:
    backend = research_jobs_backend_from_env()
    if backend == "sqlite":
        from insight_graph.research_jobs_sqlite_backend import SQLiteResearchJobsBackend

        sqlite_backend = SQLiteResearchJobsBackend(research_jobs_sqlite_path_from_env())
        sqlite_backend.initialize()
        return sqlite_backend
    return InMemoryResearchJobsBackend(
        store_path=_RESEARCH_JOBS_PATH,
        jobs=_JOBS,
        lock=_JOBS_LOCK,
    )


def configure_research_jobs_backend_from_env() -> None:
    global _NEXT_JOB_SEQUENCE, _RESEARCH_JOBS_BACKEND, _RESEARCH_JOBS_PATH

    _RESEARCH_JOBS_PATH = research_jobs_path_from_env()
    _RESEARCH_JOBS_BACKEND = _make_research_jobs_backend_from_env()
    _NEXT_JOB_SEQUENCE = _RESEARCH_JOBS_BACKEND.next_sequence()


def configure_research_jobs_in_memory_backend() -> None:
    global _RESEARCH_JOBS_BACKEND

    _RESEARCH_JOBS_BACKEND = InMemoryResearchJobsBackend(
        store_path=_RESEARCH_JOBS_PATH,
        jobs=_JOBS,
        lock=_JOBS_LOCK,
    )
    reset_research_jobs_state()


def configure_research_jobs_sqlite_backend(path: Path) -> None:
    global _NEXT_JOB_SEQUENCE, _RESEARCH_JOBS_BACKEND

    from insight_graph.research_jobs_sqlite_backend import SQLiteResearchJobsBackend

    backend = SQLiteResearchJobsBackend(path)
    backend.initialize()
    _RESEARCH_JOBS_BACKEND = backend
    _NEXT_JOB_SEQUENCE = backend.next_sequence()


def _using_sqlite_research_jobs_backend() -> bool:
    return _RESEARCH_JOBS_BACKEND.__class__.__name__ == "SQLiteResearchJobsBackend"


configure_research_jobs_backend_from_env()


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


def initialize_research_jobs(restart_timestamp: str) -> None:
    global _NEXT_JOB_SEQUENCE

    if _using_sqlite_research_jobs_backend():
        if _RESEARCH_JOBS_PATH is None:
            _RESEARCH_JOBS_BACKEND.set_next_sequence(_RESEARCH_JOBS_BACKEND.next_sequence())
            _NEXT_JOB_SEQUENCE = _RESEARCH_JOBS_BACKEND.next_sequence()
            return
        if _RESEARCH_JOBS_BACKEND.all_jobs():
            _NEXT_JOB_SEQUENCE = _RESEARCH_JOBS_BACKEND.next_sequence()
            return
        _RESEARCH_JOBS_BACKEND.import_json_store(
            _RESEARCH_JOBS_PATH,
            restart_timestamp=restart_timestamp,
        )
        _NEXT_JOB_SEQUENCE = _RESEARCH_JOBS_BACKEND.next_sequence()
        return
    if _RESEARCH_JOBS_PATH is None:
        return
    loaded = load_research_jobs(
        path=_RESEARCH_JOBS_PATH,
        restart_timestamp=restart_timestamp,
    )
    _NEXT_JOB_SEQUENCE = loaded.next_job_sequence
    _RESEARCH_JOBS_BACKEND.set_next_sequence(_NEXT_JOB_SEQUENCE)
    _JOBS.clear()
    for item in loaded.jobs:
        job = _research_job_from_store(item)
        _JOBS[job.id] = job


@dataclass(frozen=True)
class ResearchJobsStateSnapshot:
    next_job_sequence: int
    jobs: dict[str, ResearchJob]


def _research_jobs_state_snapshot_locked() -> ResearchJobsStateSnapshot:
    snapshot = _RESEARCH_JOBS_BACKEND.snapshot()
    return ResearchJobsStateSnapshot(
        next_job_sequence=snapshot.next_job_sequence,
        jobs=snapshot.jobs,
    )


def _restore_research_jobs_state_locked(snapshot: ResearchJobsStateSnapshot) -> None:
    global _NEXT_JOB_SEQUENCE

    _NEXT_JOB_SEQUENCE = snapshot.next_job_sequence
    _RESEARCH_JOBS_BACKEND.restore(snapshot)


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


def _job_timing_fields(job: ResearchJob) -> dict[str, str]:
    fields = {"created_at": job.created_at}
    if job.started_at is not None:
        fields["started_at"] = job.started_at
    if job.finished_at is not None:
        fields["finished_at"] = job.finished_at
    return fields


def _queued_job_positions_locked() -> dict[str, int]:
    queued_jobs = sorted(
        (job for job in _all_research_jobs_locked() if job.status == RESEARCH_JOB_STATUS_QUEUED),
        key=lambda item: item.created_order,
    )
    return {job.id: index for index, job in enumerate(queued_jobs, start=1)}


def _all_research_jobs_locked() -> list[ResearchJob]:
    return _RESEARCH_JOBS_BACKEND.all_jobs()


def _get_research_job_locked(job_id: str) -> ResearchJob | None:
    return _RESEARCH_JOBS_BACKEND.get(job_id)


def _active_research_job_count_locked() -> int:
    return _RESEARCH_JOBS_BACKEND.active_count()


def _job_queue_position_field(
    job: ResearchJob,
    queued_positions: dict[str, int],
) -> dict[str, int]:
    if job.status != RESEARCH_JOB_STATUS_QUEUED:
        return {}
    position = queued_positions.get(job.id)
    if position is None:
        return {}
    return {"queue_position": position}


def _job_summary(job: ResearchJob, queued_positions: dict[str, int]) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "status": job.status,
        "query": job.query,
        "preset": job.preset,
        **_job_timing_fields(job),
        **_job_queue_position_field(job, queued_positions),
    }


def _job_create_response(job: ResearchJob) -> dict[str, str]:
    return {
        "job_id": job.id,
        "status": RESEARCH_JOB_STATUS_QUEUED,
        "created_at": job.created_at,
    }


def _job_detail(job: ResearchJob, queued_positions: dict[str, int]) -> dict[str, Any]:
    response: dict[str, Any] = {
        "job_id": job.id,
        "status": job.status,
        **_job_timing_fields(job),
        **_job_queue_position_field(job, queued_positions),
    }
    if job.status == RESEARCH_JOB_STATUS_SUCCEEDED:
        response["result"] = job.result
    elif job.status == RESEARCH_JOB_STATUS_FAILED:
        response["error"] = job.error
    return response


def _jobs_list_response_locked(
    status: ResearchJobStatus | None,
    limit: int,
) -> dict[str, Any]:
    jobs = sorted(
        _all_research_jobs_locked(),
        key=lambda item: item.created_order,
        reverse=True,
    )
    if status is not None:
        jobs = [job for job in jobs if job.status == status]
    jobs = jobs[:limit]

    queued_positions = _queued_job_positions_locked()
    summaries = [_job_summary(job, queued_positions) for job in jobs]
    return {"jobs": summaries, "count": len(summaries)}


def _jobs_summary_response_locked() -> dict[str, Any]:
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
    return {
        "counts": counts,
        "active_count": _active_research_job_count_locked(),
        "active_limit": _MAX_ACTIVE_RESEARCH_JOBS,
        "queued_jobs": [_job_summary(job, queued_positions) for job in queued_jobs],
        "running_jobs": [_job_summary(job, queued_positions) for job in running_jobs],
    }


def _persist_research_jobs_best_effort_locked() -> None:
    try:
        _persist_research_jobs_locked()
    except ResearchJobsStoreError:
        pass


def _prune_finished_jobs_locked() -> None:
    _RESEARCH_JOBS_BACKEND.prune_finished()


def create_research_job(
    query: str,
    preset: ResearchPreset,
    created_at: str,
) -> dict[str, str]:
    global _NEXT_JOB_SEQUENCE

    with _JOBS_LOCK:
        if _using_sqlite_research_jobs_backend():
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
        if _active_research_job_count_locked() >= _MAX_ACTIVE_RESEARCH_JOBS:
            raise HTTPException(
                status_code=429,
                detail="Too many active research jobs.",
            )
        snapshot = _research_jobs_state_snapshot_locked()
        _NEXT_JOB_SEQUENCE += 1
        _RESEARCH_JOBS_BACKEND.set_next_sequence(_NEXT_JOB_SEQUENCE)
        job = ResearchJob(
            id=str(uuid4()),
            query=query,
            preset=preset,
            created_order=_NEXT_JOB_SEQUENCE,
            created_at=created_at,
        )
        _JOBS[job.id] = job
        _prune_finished_jobs_locked()
        try:
            _persist_research_jobs_or_500_locked()
        except HTTPException:
            _restore_research_jobs_state_locked(snapshot)
            raise
        return _job_create_response(job)


def retry_research_job(job_id: str, created_at: str) -> dict[str, str]:
    with _JOBS_LOCK:
        source = _get_research_job_locked(job_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        if source.status not in RETRYABLE_RESEARCH_JOB_STATUSES:
            raise HTTPException(
                status_code=409,
                detail="Only failed or cancelled research jobs can be retried.",
            )
    return create_research_job(
        query=source.query,
        preset=source.preset,
        created_at=created_at,
    )


def list_research_jobs(
    status: ResearchJobStatus | None,
    limit: int,
) -> dict[str, Any]:
    with _JOBS_LOCK:
        return _jobs_list_response_locked(status=status, limit=limit)


def summarize_research_jobs() -> dict[str, Any]:
    with _JOBS_LOCK:
        return _jobs_summary_response_locked()


def cancel_research_job(job_id: str, finished_at: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        if _using_sqlite_research_jobs_backend():
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
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        if job.status != RESEARCH_JOB_STATUS_QUEUED:
            raise HTTPException(
                status_code=409,
                detail="Only queued research jobs can be cancelled.",
            )
        snapshot = _research_jobs_state_snapshot_locked()
        previous_status = job.status
        previous_finished_at = job.finished_at
        job.status = RESEARCH_JOB_STATUS_CANCELLED
        job.finished_at = finished_at
        _prune_finished_jobs_locked()
        try:
            _persist_research_jobs_or_500_locked()
        except HTTPException:
            job.status = previous_status
            job.finished_at = previous_finished_at
            _restore_research_jobs_state_locked(snapshot)
            raise
        return _job_detail(job, _queued_job_positions_locked())


def get_research_job(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _get_research_job_locked(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        return _job_detail(job, _queued_job_positions_locked())


def mark_research_job_running(
    job_id: str,
    started_at: Callable[[], str],
    store_failure_finished_at: Callable[[], str],
) -> ResearchJob | None:
    with _JOBS_LOCK:
        if _using_sqlite_research_jobs_backend():
            try:
                return _RESEARCH_JOBS_BACKEND.mark_running(
                    job_id,
                    started_at=started_at(),
                )
            except ValueError:
                return None
        job = _JOBS[job_id]
        if job.status == RESEARCH_JOB_STATUS_CANCELLED:
            return None
        job.status = RESEARCH_JOB_STATUS_RUNNING
        job.started_at = started_at()
        try:
            _persist_research_jobs_locked()
        except ResearchJobsStoreError:
            job.status = RESEARCH_JOB_STATUS_FAILED
            job.finished_at = store_failure_finished_at()
            job.error = "Research job store failed."
            _prune_finished_jobs_locked()
            _persist_research_jobs_best_effort_locked()
            return None
        return job


def mark_research_job_failed(
    job: ResearchJob,
    finished_at: str,
    error: str,
) -> None:
    with _JOBS_LOCK:
        if _using_sqlite_research_jobs_backend():
            _RESEARCH_JOBS_BACKEND.mark_terminal(
                job.id,
                status=RESEARCH_JOB_STATUS_FAILED,
                finished_at=finished_at,
                result=None,
                error=error,
            )
            return
        job.status = RESEARCH_JOB_STATUS_FAILED
        job.finished_at = finished_at
        job.error = error
        _prune_finished_jobs_locked()
        _persist_research_jobs_best_effort_locked()


def mark_research_job_succeeded(
    job: ResearchJob,
    finished_at: str,
    result: dict[str, Any],
) -> None:
    with _JOBS_LOCK:
        if _using_sqlite_research_jobs_backend():
            _RESEARCH_JOBS_BACKEND.mark_terminal(
                job.id,
                status=RESEARCH_JOB_STATUS_SUCCEEDED,
                finished_at=finished_at,
                result=result,
                error=None,
            )
            return
        job.status = RESEARCH_JOB_STATUS_SUCCEEDED
        job.finished_at = finished_at
        job.result = result
        _prune_finished_jobs_locked()
        _persist_research_jobs_best_effort_locked()
