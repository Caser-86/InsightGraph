import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator
from pydantic.json_schema import SkipJsonSchema

from insight_graph.cli import (
    LIVE_LLM_PRESET_DEFAULTS,
    ResearchPreset,
    _build_research_json_payload,
)
from insight_graph.graph import run_research
from insight_graph.research_jobs_store import (
    ResearchJobsStoreError,
    load_research_jobs,
    research_jobs_path_from_env,
    save_research_jobs,
)

router = APIRouter()


def create_app() -> FastAPI:
    application = FastAPI(title="InsightGraph API")
    application.include_router(router)
    return application

# Presets use process env, so this synchronous MVP serializes /research execution.
_RESEARCH_ENV_LOCK = Lock()
_JOBS_LOCK = Lock()
_JOB_EXECUTOR = ThreadPoolExecutor(max_workers=1)
_MAX_RESEARCH_JOBS = 100
_MAX_ACTIVE_RESEARCH_JOBS = 100
_RESEARCH_JOB_STATUS_QUEUED = "queued"
_RESEARCH_JOB_STATUS_RUNNING = "running"
_RESEARCH_JOB_STATUS_SUCCEEDED = "succeeded"
_RESEARCH_JOB_STATUS_FAILED = "failed"
_RESEARCH_JOB_STATUS_CANCELLED = "cancelled"
_RESEARCH_JOB_STATUSES = (
    _RESEARCH_JOB_STATUS_QUEUED,
    _RESEARCH_JOB_STATUS_RUNNING,
    _RESEARCH_JOB_STATUS_SUCCEEDED,
    _RESEARCH_JOB_STATUS_FAILED,
    _RESEARCH_JOB_STATUS_CANCELLED,
)
ResearchJobStatusQuery = Annotated[
    Literal[
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
    ]
    | None,
    Query(description="Filter jobs by status. Omit to return all retained jobs."),
]
ResearchJobsLimitQuery = Annotated[
    int,
    Query(
        ge=1,
        le=100,
        description=(
            "Maximum number of jobs to return. The response count is the "
            "returned count, not a total."
        ),
    ),
]
_ACTIVE_RESEARCH_JOB_STATUSES = {
    _RESEARCH_JOB_STATUS_QUEUED,
    _RESEARCH_JOB_STATUS_RUNNING,
}
_TERMINAL_RESEARCH_JOB_STATUSES = {
    _RESEARCH_JOB_STATUS_SUCCEEDED,
    _RESEARCH_JOB_STATUS_FAILED,
    _RESEARCH_JOB_STATUS_CANCELLED,
}
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
    status: str = _RESEARCH_JOB_STATUS_QUEUED
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class ResearchRequest(BaseModel):
    query: str
    preset: ResearchPreset = ResearchPreset.offline

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be blank")
        return stripped


class ResearchJobCreateResponse(BaseModel):
    job_id: str
    status: str
    created_at: str


class ResearchJobSummary(BaseModel):
    job_id: str
    status: str
    query: str
    preset: ResearchPreset
    created_at: str
    started_at: str | SkipJsonSchema[None] = None
    finished_at: str | SkipJsonSchema[None] = None
    queue_position: int | SkipJsonSchema[None] = None


class ResearchJobDetailResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    started_at: str | SkipJsonSchema[None] = None
    finished_at: str | SkipJsonSchema[None] = None
    queue_position: int | SkipJsonSchema[None] = None
    result: dict[str, Any] | SkipJsonSchema[None] = None
    error: str | SkipJsonSchema[None] = None


class ResearchJobsListResponse(BaseModel):
    jobs: list[ResearchJobSummary]
    count: int


class ResearchJobsSummaryResponse(BaseModel):
    counts: dict[str, int]
    active_count: int
    active_limit: int
    queued_jobs: list[ResearchJobSummary]
    running_jobs: list[ResearchJobSummary]


_RESEARCH_JOBS_TAG = "research jobs"
_RESEARCH_JOB_NOT_FOUND_RESPONSE = {
    "description": "Research job not found.",
    "content": {"application/json": {"example": {"detail": "Research job not found."}}},
}
_RESEARCH_JOB_STORE_FAILED_RESPONSE = {
    "description": "Research job store failed.",
    "content": {
        "application/json": {"example": {"detail": "Research job store failed."}}
    },
}
_TOO_MANY_ACTIVE_RESEARCH_JOBS_RESPONSE = {
    "description": "Too many active research jobs.",
    "content": {
        "application/json": {"example": {"detail": "Too many active research jobs."}}
    },
}
_RESEARCH_JOB_CANCEL_CONFLICT_RESPONSE = {
    "description": "Only queued research jobs can be cancelled.",
    "content": {
        "application/json": {
            "example": {"detail": "Only queued research jobs can be cancelled."}
        }
    },
}
_RESEARCH_JOB_CREATE_EXAMPLE = {
    "job_id": "job-123",
    "status": "queued",
    "created_at": "2026-04-27T10:00:00Z",
}
_RESEARCH_JOB_LIST_EXAMPLE = {
    "jobs": [
        {
            "job_id": "job-123",
            "status": "queued",
            "query": "Compare AI coding agents",
            "preset": "offline",
            "created_at": "2026-04-27T10:00:00Z",
            "queue_position": 1,
        }
    ],
    "count": 1,
}
_RESEARCH_JOBS_SUMMARY_EXAMPLE = {
    "counts": {
        "queued": 1,
        "running": 1,
        "succeeded": 0,
        "failed": 0,
        "cancelled": 0,
        "total": 2,
    },
    "active_count": 2,
    "active_limit": 100,
    "queued_jobs": [
        {
            "job_id": "job-123",
            "status": "queued",
            "query": "Compare AI coding agents",
            "preset": "offline",
            "created_at": "2026-04-27T10:00:00Z",
            "queue_position": 1,
        }
    ],
    "running_jobs": [
        {
            "job_id": "job-456",
            "status": "running",
            "query": "Analyze market signals",
            "preset": "offline",
            "created_at": "2026-04-27T10:01:00Z",
            "started_at": "2026-04-27T10:01:01Z",
        }
    ],
}
_RESEARCH_JOB_DETAIL_EXAMPLE = {
    "job_id": "job-789",
    "status": "succeeded",
    "created_at": "2026-04-27T10:02:00Z",
    "started_at": "2026-04-27T10:02:01Z",
    "finished_at": "2026-04-27T10:02:05Z",
    "result": {"report_markdown": "# InsightGraph Research Report\n"},
}
_RESEARCH_JOB_CANCEL_EXAMPLE = {
    "job_id": "job-123",
    "status": "cancelled",
    "created_at": "2026-04-27T10:00:00Z",
    "finished_at": "2026-04-27T10:00:10Z",
}


@contextmanager
def _research_preset_environment(preset: ResearchPreset) -> Iterator[None]:
    if preset == ResearchPreset.offline:
        yield
        return

    previous_values = {name: os.environ.get(name) for name in LIVE_LLM_PRESET_DEFAULTS}
    try:
        for name, value in LIVE_LLM_PRESET_DEFAULTS.items():
            os.environ.setdefault(name, value)
        yield
    finally:
        for name, value in previous_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _current_utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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


def initialize_research_jobs() -> None:
    global _NEXT_JOB_SEQUENCE

    if _RESEARCH_JOBS_PATH is None:
        return
    loaded = load_research_jobs(
        path=_RESEARCH_JOBS_PATH,
        restart_timestamp=_current_utc_timestamp(),
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


initialize_research_jobs()


def _job_timing_fields(job: ResearchJob) -> dict[str, str]:
    fields = {"created_at": job.created_at}
    if job.started_at is not None:
        fields["started_at"] = job.started_at
    if job.finished_at is not None:
        fields["finished_at"] = job.finished_at
    return fields


def _queued_job_positions_locked() -> dict[str, int]:
    queued_jobs = sorted(
        (job for job in _JOBS.values() if job.status == _RESEARCH_JOB_STATUS_QUEUED),
        key=lambda item: item.created_order,
    )
    return {job.id: index for index, job in enumerate(queued_jobs, start=1)}


def _active_research_job_count_locked() -> int:
    return sum(1 for job in _JOBS.values() if job.status in _ACTIVE_RESEARCH_JOB_STATUSES)


def _job_queue_position_field(
    job: ResearchJob,
    queued_positions: dict[str, int],
) -> dict[str, int]:
    if job.status != _RESEARCH_JOB_STATUS_QUEUED:
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
        "status": _RESEARCH_JOB_STATUS_QUEUED,
        "created_at": job.created_at,
    }


def _job_detail(job: ResearchJob, queued_positions: dict[str, int]) -> dict[str, Any]:
    response: dict[str, Any] = {
        "job_id": job.id,
        "status": job.status,
        **_job_timing_fields(job),
        **_job_queue_position_field(job, queued_positions),
    }
    if job.status == _RESEARCH_JOB_STATUS_SUCCEEDED:
        response["result"] = job.result
    elif job.status == _RESEARCH_JOB_STATUS_FAILED:
        response["error"] = job.error
    return response


def _jobs_list_response_locked(
    status: ResearchJobStatusQuery | None,
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
    counts = {status: 0 for status in _RESEARCH_JOB_STATUSES}
    for job in _JOBS.values():
        counts[job.status] = counts.get(job.status, 0) + 1
    counts["total"] = len(_JOBS)

    queued_positions = _queued_job_positions_locked()
    queued_jobs = sorted(
        (job for job in _JOBS.values() if job.status == _RESEARCH_JOB_STATUS_QUEUED),
        key=lambda item: item.created_order,
    )
    running_jobs = sorted(
        (job for job in _JOBS.values() if job.status == _RESEARCH_JOB_STATUS_RUNNING),
        key=lambda item: item.created_order,
    )
    return {
        "counts": counts,
        "active_count": _active_research_job_count_locked(),
        "active_limit": _MAX_ACTIVE_RESEARCH_JOBS,
        "queued_jobs": [_job_summary(job, queued_positions) for job in queued_jobs],
        "running_jobs": [_job_summary(job, queued_positions) for job in running_jobs],
    }


@router.post("/research")
def research(request: ResearchRequest) -> dict[str, Any]:
    try:
        with _RESEARCH_ENV_LOCK:
            with _research_preset_environment(request.preset):
                state = run_research(request.query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Research workflow failed.") from exc
    return _build_research_json_payload(state)


@router.post(
    "/research/jobs",
    status_code=202,
    response_model=ResearchJobCreateResponse,
    response_model_exclude_none=True,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Create research job",
    description=(
        "Queue a research workflow for background execution. Jobs start as queued and "
        "can be inspected with the job detail endpoint."
    ),
    responses={
        202: {"content": {"application/json": {"example": _RESEARCH_JOB_CREATE_EXAMPLE}}},
        429: _TOO_MANY_ACTIVE_RESEARCH_JOBS_RESPONSE,
        500: _RESEARCH_JOB_STORE_FAILED_RESPONSE,
    },
)
def create_research_job(request: ResearchRequest) -> dict[str, str]:
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
            query=request.query,
            preset=request.preset,
            created_order=_NEXT_JOB_SEQUENCE,
            created_at=_current_utc_timestamp(),
        )
        _JOBS[job.id] = job
        _prune_finished_jobs_locked()
        try:
            _persist_research_jobs_or_500_locked()
        except HTTPException:
            _restore_research_jobs_state_locked(snapshot)
            raise
    _JOB_EXECUTOR.submit(_run_research_job, job.id)
    return _job_create_response(job)


@router.get(
    "/research/jobs",
    response_model=ResearchJobsListResponse,
    response_model_exclude_none=True,
    tags=[_RESEARCH_JOBS_TAG],
    summary="List research jobs",
    description=(
        "Return retained research jobs ordered newest first. Optional status filtering "
        "does not change queued job positions."
    ),
    responses={
        200: {"content": {"application/json": {"example": _RESEARCH_JOB_LIST_EXAMPLE}}},
    },
)
def list_research_jobs(
    status: ResearchJobStatusQuery = None,
    limit: ResearchJobsLimitQuery = 100,
) -> dict[str, Any]:
    with _JOBS_LOCK:
        return _jobs_list_response_locked(status=status, limit=limit)


@router.get(
    "/research/jobs/summary",
    response_model=ResearchJobsSummaryResponse,
    response_model_exclude_none=True,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Summarize research jobs",
    description=(
        "Return job counts plus queued and running job summaries for monitoring active work."
    ),
    responses={
        200: {
            "content": {"application/json": {"example": _RESEARCH_JOBS_SUMMARY_EXAMPLE}}
        },
    },
)
def summarize_research_jobs() -> dict[str, Any]:
    with _JOBS_LOCK:
        return _jobs_summary_response_locked()


@router.post(
    "/research/jobs/{job_id}/cancel",
    response_model=ResearchJobDetailResponse,
    response_model_exclude_none=True,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Cancel queued research job",
    description=(
        "Cancel a queued research job. Running and terminal jobs are not cancellable."
    ),
    responses={
        200: {"content": {"application/json": {"example": _RESEARCH_JOB_CANCEL_EXAMPLE}}},
        404: _RESEARCH_JOB_NOT_FOUND_RESPONSE,
        409: _RESEARCH_JOB_CANCEL_CONFLICT_RESPONSE,
        500: _RESEARCH_JOB_STORE_FAILED_RESPONSE,
    },
)
def cancel_research_job(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        if job.status != _RESEARCH_JOB_STATUS_QUEUED:
            raise HTTPException(
                status_code=409,
                detail="Only queued research jobs can be cancelled.",
            )
        snapshot = _research_jobs_state_snapshot_locked()
        previous_status = job.status
        previous_finished_at = job.finished_at
        job.status = _RESEARCH_JOB_STATUS_CANCELLED
        job.finished_at = _current_utc_timestamp()
        _prune_finished_jobs_locked()
        try:
            _persist_research_jobs_or_500_locked()
        except HTTPException:
            job.status = previous_status
            job.finished_at = previous_finished_at
            _restore_research_jobs_state_locked(snapshot)
            raise
        return _job_detail(job, _queued_job_positions_locked())


@router.get(
    "/research/jobs/{job_id}",
    response_model=ResearchJobDetailResponse,
    response_model_exclude_none=True,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Get research job",
    description=(
        "Return one research job. Succeeded jobs include result, failed jobs include "
        "a safe error message, and queued jobs include queue position."
    ),
    responses={
        200: {"content": {"application/json": {"example": _RESEARCH_JOB_DETAIL_EXAMPLE}}},
        404: _RESEARCH_JOB_NOT_FOUND_RESPONSE,
    },
)
def get_research_job(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        return _job_detail(job, _queued_job_positions_locked())


def _persist_research_jobs_best_effort_locked() -> None:
    try:
        _persist_research_jobs_locked()
    except ResearchJobsStoreError:
        pass


def _mark_research_job_running_locked(job: ResearchJob) -> bool:
    if job.status == _RESEARCH_JOB_STATUS_CANCELLED:
        return False
    job.status = _RESEARCH_JOB_STATUS_RUNNING
    job.started_at = _current_utc_timestamp()
    try:
        _persist_research_jobs_locked()
    except ResearchJobsStoreError:
        job.status = _RESEARCH_JOB_STATUS_FAILED
        job.finished_at = _current_utc_timestamp()
        job.error = "Research job store failed."
        _prune_finished_jobs_locked()
        _persist_research_jobs_best_effort_locked()
        return False
    return True


def _mark_research_job_failed_locked(job: ResearchJob, error: str) -> None:
    job.status = _RESEARCH_JOB_STATUS_FAILED
    job.finished_at = _current_utc_timestamp()
    job.error = error
    _prune_finished_jobs_locked()
    _persist_research_jobs_best_effort_locked()


def _mark_research_job_succeeded_locked(
    job: ResearchJob,
    result: dict[str, Any],
) -> None:
    job.status = _RESEARCH_JOB_STATUS_SUCCEEDED
    job.finished_at = _current_utc_timestamp()
    job.result = result
    _prune_finished_jobs_locked()
    _persist_research_jobs_best_effort_locked()


def _run_research_job(job_id: str) -> None:
    with _JOBS_LOCK:
        job = _JOBS[job_id]
        if not _mark_research_job_running_locked(job):
            return

    try:
        with _RESEARCH_ENV_LOCK:
            with _research_preset_environment(job.preset):
                state = run_research(job.query)
        result = _build_research_json_payload(state)
    except Exception:
        with _JOBS_LOCK:
            _mark_research_job_failed_locked(
                job,
                "Research workflow failed.",
            )
        return

    with _JOBS_LOCK:
        _mark_research_job_succeeded_locked(job, result)


def _prune_finished_jobs_locked() -> None:
    finished_jobs = [
        job
        for job in _JOBS.values()
        if job.status in _TERMINAL_RESEARCH_JOB_STATUSES
    ]
    overflow = len(finished_jobs) - _MAX_RESEARCH_JOBS
    if overflow <= 0:
        return

    for job in sorted(finished_jobs, key=lambda item: item.created_order)[:overflow]:
        del _JOBS[job.id]


app = create_app()
