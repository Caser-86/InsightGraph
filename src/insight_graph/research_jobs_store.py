import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RESEARCH_JOBS_PATH_ENV = "INSIGHT_GRAPH_RESEARCH_JOBS_PATH"
RESTART_FAILURE_ERROR = "Research job did not complete before server restart."
_REQUIRED_JOB_FIELDS = {
    "id",
    "query",
    "preset",
    "created_order",
    "created_at",
    "status",
    "started_at",
    "finished_at",
    "result",
    "error",
}


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


def serialize_research_job(job: Any) -> dict[str, Any]:
    preset = job.preset.value if hasattr(job.preset, "value") else job.preset
    return {
        "id": job.id,
        "query": job.query,
        "preset": preset,
        "created_order": job.created_order,
        "created_at": job.created_at,
        "status": job.status,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result": job.result,
        "error": job.error,
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
    if not isinstance(next_job_sequence, int) or not isinstance(jobs, list):
        raise ResearchJobsStoreError("Research jobs store schema is invalid.")

    loaded_jobs = [_load_job(item, restart_timestamp) for item in jobs]
    return LoadedResearchJobs(
        next_job_sequence=next_job_sequence,
        jobs=loaded_jobs,
    )


def _load_job(item: object, restart_timestamp: str) -> dict[str, Any]:
    if not isinstance(item, dict) or set(item) != _REQUIRED_JOB_FIELDS:
        raise ResearchJobsStoreError("Research jobs store job schema is invalid.")
    job = dict(item)
    if job["status"] in {"queued", "running"}:
        job["status"] = "failed"
        job["finished_at"] = restart_timestamp
        job["error"] = RESTART_FAILURE_ERROR
    return job


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
