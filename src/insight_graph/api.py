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

from fastapi import FastAPI, HTTPException, Query
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

app = FastAPI(title="InsightGraph API")

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
ResearchJobStatusQuery = Literal[
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
]
ResearchJobsLimitQuery = Annotated[int, Query(ge=1, le=100)]
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


@app.get("/health")
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


def _load_research_jobs_from_store() -> None:
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


_load_research_jobs_from_store()


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


@app.post("/research")
def research(request: ResearchRequest) -> dict[str, Any]:
    try:
        with _RESEARCH_ENV_LOCK:
            with _research_preset_environment(request.preset):
                state = run_research(request.query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Research workflow failed.") from exc
    return _build_research_json_payload(state)


@app.post(
    "/research/jobs",
    status_code=202,
    response_model=ResearchJobCreateResponse,
    response_model_exclude_none=True,
)
def create_research_job(request: ResearchRequest) -> dict[str, str]:
    global _NEXT_JOB_SEQUENCE

    with _JOBS_LOCK:
        if _active_research_job_count_locked() >= _MAX_ACTIVE_RESEARCH_JOBS:
            raise HTTPException(
                status_code=429,
                detail="Too many active research jobs.",
            )
        previous_sequence = _NEXT_JOB_SEQUENCE
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
            _JOBS.pop(job.id, None)
            _NEXT_JOB_SEQUENCE = previous_sequence
            raise
    _JOB_EXECUTOR.submit(_run_research_job, job.id)
    return _job_create_response(job)


@app.get(
    "/research/jobs",
    response_model=ResearchJobsListResponse,
    response_model_exclude_none=True,
)
def list_research_jobs(
    status: ResearchJobStatusQuery | None = None,
    limit: ResearchJobsLimitQuery = 100,
) -> dict[str, Any]:
    with _JOBS_LOCK:
        return _jobs_list_response_locked(status=status, limit=limit)


@app.get(
    "/research/jobs/summary",
    response_model=ResearchJobsSummaryResponse,
    response_model_exclude_none=True,
)
def summarize_research_jobs() -> dict[str, Any]:
    with _JOBS_LOCK:
        return _jobs_summary_response_locked()


@app.post(
    "/research/jobs/{job_id}/cancel",
    response_model=ResearchJobDetailResponse,
    response_model_exclude_none=True,
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
        job.status = _RESEARCH_JOB_STATUS_CANCELLED
        job.finished_at = _current_utc_timestamp()
        _prune_finished_jobs_locked()
        _persist_research_jobs_or_500_locked()
        return _job_detail(job, _queued_job_positions_locked())


@app.get(
    "/research/jobs/{job_id}",
    response_model=ResearchJobDetailResponse,
    response_model_exclude_none=True,
)
def get_research_job(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        return _job_detail(job, _queued_job_positions_locked())


def _run_research_job(job_id: str) -> None:
    with _JOBS_LOCK:
        job = _JOBS[job_id]
        if job.status == _RESEARCH_JOB_STATUS_CANCELLED:
            return
        job.status = _RESEARCH_JOB_STATUS_RUNNING
        job.started_at = _current_utc_timestamp()
        _persist_research_jobs_locked()

    try:
        with _RESEARCH_ENV_LOCK:
            with _research_preset_environment(job.preset):
                state = run_research(job.query)
        result = _build_research_json_payload(state)
    except Exception:
        with _JOBS_LOCK:
            job.status = _RESEARCH_JOB_STATUS_FAILED
            job.finished_at = _current_utc_timestamp()
            job.error = "Research workflow failed."
            _prune_finished_jobs_locked()
            _persist_research_jobs_locked()
        return

    with _JOBS_LOCK:
        job.status = _RESEARCH_JOB_STATUS_SUCCEEDED
        job.finished_at = _current_utc_timestamp()
        job.result = result
        _prune_finished_jobs_locked()
        _persist_research_jobs_locked()


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
