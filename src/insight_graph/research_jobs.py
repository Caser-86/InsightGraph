from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException

from insight_graph.cli import ResearchPreset
from insight_graph.research_jobs_store import (
    ResearchJobsStoreError,
    load_research_jobs,
    research_jobs_path_from_env,
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
_JOBS_LOCK = Lock()
_MAX_RESEARCH_JOBS = 100
_MAX_ACTIVE_RESEARCH_JOBS = 100
_NEXT_JOB_SEQUENCE = 0
_JOBS: dict[str, "ResearchJob"] = {}
_RESEARCH_JOBS_PATH: Path | None = research_jobs_path_from_env()


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

    if _RESEARCH_JOBS_PATH is None:
        return
    loaded = load_research_jobs(
        path=_RESEARCH_JOBS_PATH,
        restart_timestamp=restart_timestamp,
    )
    _NEXT_JOB_SEQUENCE = loaded.next_job_sequence
    _JOBS.clear()
    for item in loaded.jobs:
        job = _research_job_from_store(item)
        _JOBS[job.id] = job


@dataclass(frozen=True)
class ResearchJobsStateSnapshot:
    next_job_sequence: int
    jobs: dict[str, ResearchJob]


def _research_jobs_state_snapshot_locked() -> ResearchJobsStateSnapshot:
    return ResearchJobsStateSnapshot(
        next_job_sequence=_NEXT_JOB_SEQUENCE,
        jobs=dict(_JOBS),
    )


def _restore_research_jobs_state_locked(snapshot: ResearchJobsStateSnapshot) -> None:
    global _NEXT_JOB_SEQUENCE

    _NEXT_JOB_SEQUENCE = snapshot.next_job_sequence
    _JOBS.clear()
    _JOBS.update(snapshot.jobs)


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
        (job for job in _JOBS.values() if job.status == RESEARCH_JOB_STATUS_QUEUED),
        key=lambda item: item.created_order,
    )
    return {job.id: index for index, job in enumerate(queued_jobs, start=1)}


def _active_research_job_count_locked() -> int:
    return sum(1 for job in _JOBS.values() if job.status in ACTIVE_RESEARCH_JOB_STATUSES)


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
        _JOBS.values(),
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
    counts = {status: 0 for status in RESEARCH_JOB_STATUSES}
    for job in _JOBS.values():
        counts[job.status] = counts.get(job.status, 0) + 1
    counts["total"] = len(_JOBS)

    queued_positions = _queued_job_positions_locked()
    queued_jobs = sorted(
        (job for job in _JOBS.values() if job.status == RESEARCH_JOB_STATUS_QUEUED),
        key=lambda item: item.created_order,
    )
    running_jobs = sorted(
        (job for job in _JOBS.values() if job.status == RESEARCH_JOB_STATUS_RUNNING),
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
    finished_jobs = [
        job for job in _JOBS.values() if job.status in TERMINAL_RESEARCH_JOB_STATUSES
    ]
    overflow = len(finished_jobs) - _MAX_RESEARCH_JOBS
    if overflow <= 0:
        return

    for job in sorted(finished_jobs, key=lambda item: item.created_order)[:overflow]:
        del _JOBS[job.id]


def create_research_job(
    query: str,
    preset: ResearchPreset,
    created_at: str,
) -> dict[str, str]:
    global _NEXT_JOB_SEQUENCE

    with _JOBS_LOCK:
        if _active_research_job_count_locked() >= _MAX_ACTIVE_RESEARCH_JOBS:
            raise HTTPException(
                status_code=429,
                detail="Too many active research jobs.",
            )
        snapshot = _research_jobs_state_snapshot_locked()
        _NEXT_JOB_SEQUENCE += 1
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
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        return _job_detail(job, _queued_job_positions_locked())


def mark_research_job_running(
    job_id: str,
    started_at: Callable[[], str],
    store_failure_finished_at: Callable[[], str],
) -> ResearchJob | None:
    with _JOBS_LOCK:
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
        job.status = RESEARCH_JOB_STATUS_SUCCEEDED
        job.finished_at = finished_at
        job.result = result
        _prune_finished_jobs_locked()
        _persist_research_jobs_best_effort_locked()
