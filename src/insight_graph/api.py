import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

from insight_graph.cli import (
    LIVE_LLM_PRESET_DEFAULTS,
    ResearchPreset,
    _build_research_json_payload,
)
from insight_graph.graph import run_research

app = FastAPI(title="InsightGraph API")

# Presets use process env, so this synchronous MVP serializes /research execution.
_RESEARCH_ENV_LOCK = Lock()
_JOBS_LOCK = Lock()
_JOB_EXECUTOR = ThreadPoolExecutor(max_workers=1)
_MAX_RESEARCH_JOBS = 100
_NEXT_JOB_SEQUENCE = 0
_JOBS: dict[str, "ResearchJob"] = {}


@dataclass
class ResearchJob:
    id: str
    query: str
    preset: ResearchPreset
    created_order: int
    created_at: str
    status: str = "queued"
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


def _job_timing_fields(job: ResearchJob) -> dict[str, str]:
    fields = {"created_at": job.created_at}
    if job.started_at is not None:
        fields["started_at"] = job.started_at
    if job.finished_at is not None:
        fields["finished_at"] = job.finished_at
    return fields


def _job_summary(job: ResearchJob) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "status": job.status,
        "query": job.query,
        "preset": job.preset,
        **_job_timing_fields(job),
    }


def _job_detail(job: ResearchJob) -> dict[str, Any]:
    response: dict[str, Any] = {
        "job_id": job.id,
        "status": job.status,
        **_job_timing_fields(job),
    }
    if job.status == "succeeded":
        response["result"] = job.result
    elif job.status == "failed":
        response["error"] = job.error
    return response


@app.post("/research")
def research(request: ResearchRequest) -> dict[str, Any]:
    try:
        with _RESEARCH_ENV_LOCK:
            with _research_preset_environment(request.preset):
                state = run_research(request.query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Research workflow failed.") from exc
    return _build_research_json_payload(state)


@app.post("/research/jobs", status_code=202)
def create_research_job(request: ResearchRequest) -> dict[str, str]:
    global _NEXT_JOB_SEQUENCE

    with _JOBS_LOCK:
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
    _JOB_EXECUTOR.submit(_run_research_job, job.id)
    return {
        "job_id": job.id,
        "status": "queued",
        "created_at": job.created_at,
    }


@app.get("/research/jobs")
def list_research_jobs() -> dict[str, Any]:
    with _JOBS_LOCK:
        jobs = sorted(
            _JOBS.values(),
            key=lambda item: item.created_order,
            reverse=True,
        )
        summaries = [_job_summary(job) for job in jobs]
    return {"jobs": summaries, "count": len(summaries)}


@app.post("/research/jobs/{job_id}/cancel")
def cancel_research_job(job_id: str) -> dict[str, str]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        if job.status != "queued":
            raise HTTPException(
                status_code=409,
                detail="Only queued research jobs can be cancelled.",
            )
        job.status = "cancelled"
        job.finished_at = _current_utc_timestamp()
        _prune_finished_jobs_locked()
        return _job_detail(job)


@app.get("/research/jobs/{job_id}")
def get_research_job(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        return _job_detail(job)


def _run_research_job(job_id: str) -> None:
    with _JOBS_LOCK:
        job = _JOBS[job_id]
        if job.status == "cancelled":
            return
        job.status = "running"
        job.started_at = _current_utc_timestamp()

    try:
        with _RESEARCH_ENV_LOCK:
            with _research_preset_environment(job.preset):
                state = run_research(job.query)
        result = _build_research_json_payload(state)
    except Exception:
        with _JOBS_LOCK:
            job.status = "failed"
            job.finished_at = _current_utc_timestamp()
            job.error = "Research workflow failed."
            _prune_finished_jobs_locked()
        return

    with _JOBS_LOCK:
        job.status = "succeeded"
        job.finished_at = _current_utc_timestamp()
        job.result = result
        _prune_finished_jobs_locked()


def _prune_finished_jobs_locked() -> None:
    finished_jobs = [
        job
        for job in _JOBS.values()
        if job.status in {"succeeded", "failed", "cancelled"}
    ]
    overflow = len(finished_jobs) - _MAX_RESEARCH_JOBS
    if overflow <= 0:
        return

    for job in sorted(finished_jobs, key=lambda item: item.created_order)[:overflow]:
        del _JOBS[job.id]
