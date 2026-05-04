import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RESEARCH_JOBS_PATH_ENV = "INSIGHT_GRAPH_RESEARCH_JOBS_PATH"
RESEARCH_JOBS_BACKEND_ENV = "INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND"
RESEARCH_JOBS_SQLITE_PATH_ENV = "INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH"
RESTART_FAILURE_ERROR = "Research job did not complete before server restart."
_REQUIRED_JOB_FIELDS = {
    "id",
    "query",
    "preset",
    "report_intensity",
    "created_order",
    "created_at",
    "status",
    "started_at",
    "finished_at",
    "result",
    "error",
    "events",
}
_LEGACY_JOB_FIELDS = _REQUIRED_JOB_FIELDS - {"events", "report_intensity"}
_RESEARCH_JOB_STATUSES = {"queued", "running", "succeeded", "failed", "cancelled"}
_RESEARCH_PRESETS = {"offline", "live-llm", "live-research"}
_REPORT_INTENSITIES = {"concise", "standard", "deep"}


class ResearchJobsStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedResearchJobs:
    next_job_sequence: int
    jobs: list[dict[str, Any]]


def research_jobs_path_from_env() -> Path | None:
    value = os.environ.get(RESEARCH_JOBS_PATH_ENV)
    if value is None or not value.strip():
        return None
    return Path(value)


def research_jobs_backend_from_env() -> str:
    value = os.environ.get(RESEARCH_JOBS_BACKEND_ENV, "memory").strip().lower()
    if value in {"", "memory"}:
        return "memory"
    if value == "sqlite":
        return "sqlite"
    raise ResearchJobsStoreError(f"Unknown research jobs backend: {value}")


def research_jobs_sqlite_path_from_env() -> Path:
    value = os.environ.get(RESEARCH_JOBS_SQLITE_PATH_ENV)
    if value is None or not value.strip():
        raise ResearchJobsStoreError("SQLite research jobs path is required.")
    return Path(value)


def serialize_research_job(job: Any) -> dict[str, Any]:
    preset = job.preset.value if hasattr(job.preset, "value") else job.preset
    raw_report_intensity = getattr(job, "report_intensity", "standard")
    report_intensity = (
        raw_report_intensity.value
        if hasattr(raw_report_intensity, "value")
        else raw_report_intensity
    )
    return {
        "id": job.id,
        "query": job.query,
        "preset": preset,
        "report_intensity": report_intensity,
        "created_order": job.created_order,
        "created_at": job.created_at,
        "status": job.status,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result": job.result,
        "error": job.error,
        "events": getattr(job, "events", None) or [],
    }


def save_research_jobs(path: Path, jobs: list[Any], next_job_sequence: int) -> None:
    payload = {
        "jobs": [serialize_research_job(job) for job in jobs],
        "next_job_sequence": next_job_sequence,
    }
    try:
        _atomic_write_json(path, payload)
    except OSError as exc:
        raise ResearchJobsStoreError("Research jobs store write failed.") from exc


def load_research_jobs(path: Path, restart_timestamp: str) -> LoadedResearchJobs:
    if not path.exists():
        return LoadedResearchJobs(next_job_sequence=0, jobs=[])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchJobsStoreError("Research jobs store load failed.") from exc

    if not isinstance(payload, dict):
        raise ResearchJobsStoreError("Research jobs store payload must be an object.")
    next_job_sequence = payload.get("next_job_sequence")
    jobs = payload.get("jobs")
    if not _is_int(next_job_sequence) or not isinstance(jobs, list):
        raise ResearchJobsStoreError("Research jobs store schema is invalid.")

    loaded_jobs = [_load_job(item, restart_timestamp) for item in jobs]
    return LoadedResearchJobs(
        next_job_sequence=next_job_sequence,
        jobs=loaded_jobs,
    )


def _load_job(item: object, restart_timestamp: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ResearchJobsStoreError("Research jobs store job schema is invalid.")
    fields = set(item)
    if fields != _REQUIRED_JOB_FIELDS and fields != _LEGACY_JOB_FIELDS:
        raise ResearchJobsStoreError("Research jobs store job schema is invalid.")
    job = dict(item)
    job.setdefault("events", [])
    job.setdefault("report_intensity", "standard")
    _validate_job_values(job)
    if job["status"] in {"queued", "running"}:
        job["status"] = "failed"
        job["finished_at"] = restart_timestamp
        job["error"] = RESTART_FAILURE_ERROR
    return job


def _validate_job_values(job: dict[str, Any]) -> None:
    if not isinstance(job["id"], str):
        raise ResearchJobsStoreError("Research jobs store job id is invalid.")
    if not isinstance(job["query"], str):
        raise ResearchJobsStoreError("Research jobs store job query is invalid.")
    if not isinstance(job["preset"], str) or job["preset"] not in _RESEARCH_PRESETS:
        raise ResearchJobsStoreError("Research jobs store job preset is invalid.")
    if (
        not isinstance(job["report_intensity"], str)
        or job["report_intensity"] not in _REPORT_INTENSITIES
    ):
        raise ResearchJobsStoreError("Research jobs store job intensity is invalid.")
    if not _is_int(job["created_order"]):
        raise ResearchJobsStoreError("Research jobs store job created_order is invalid.")
    if not isinstance(job["created_at"], str):
        raise ResearchJobsStoreError("Research jobs store job created_at is invalid.")
    if not isinstance(job["status"], str) or job["status"] not in _RESEARCH_JOB_STATUSES:
        raise ResearchJobsStoreError("Research jobs store job status is invalid.")
    if job["started_at"] is not None and not isinstance(job["started_at"], str):
        raise ResearchJobsStoreError("Research jobs store job started_at is invalid.")
    if job["finished_at"] is not None and not isinstance(job["finished_at"], str):
        raise ResearchJobsStoreError("Research jobs store job finished_at is invalid.")
    if job["result"] is not None and not isinstance(job["result"], dict):
        raise ResearchJobsStoreError("Research jobs store job result is invalid.")
    if job["error"] is not None and not isinstance(job["error"], str):
        raise ResearchJobsStoreError("Research jobs store job error is invalid.")
    if not isinstance(job["events"], list) or not all(
        isinstance(event, dict) for event in job["events"]
    ):
        raise ResearchJobsStoreError("Research jobs store job events are invalid.")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, sort_keys=True)
            file.write("\n")
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise
