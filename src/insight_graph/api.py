import hmac
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from html import escape as html_escape
from threading import Event, Lock, Thread
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, field_validator
from pydantic.json_schema import SkipJsonSchema

from insight_graph.cli import (
    LIVE_LLM_PRESET_DEFAULTS,
    ResearchPreset,
    _build_research_json_payload,
)
from insight_graph.dashboard import dashboard_html
from insight_graph.graph import run_research
from insight_graph.research_jobs import (
    RESEARCH_JOB_HEARTBEAT_INTERVAL_SECONDS,
    RESEARCH_JOB_LEASE_TTL_SECONDS,
    ResearchJobStatus,
    configure_research_jobs_backend_from_env,
    heartbeat_research_job,
    initialize_research_jobs,
    mark_research_job_failed,
    mark_research_job_running,
    mark_research_job_succeeded,
    research_jobs_worker_id,
    using_sqlite_research_jobs_backend,
)
from insight_graph.research_jobs import (
    cancel_research_job as cancel_research_job_record,
)
from insight_graph.research_jobs import (
    create_research_job as create_research_job_record,
)
from insight_graph.research_jobs import (
    get_research_job as get_research_job_record,
)
from insight_graph.research_jobs import (
    list_research_jobs as list_research_job_records,
)
from insight_graph.research_jobs import (
    retry_research_job as retry_research_job_record,
)
from insight_graph.research_jobs import (
    summarize_research_jobs as summarize_research_jobs_state,
)

router = APIRouter()


def create_app() -> FastAPI:
    application = FastAPI(title="InsightGraph API")
    application.include_router(router)
    return application


# Presets use process env, so this synchronous MVP serializes /research execution.
_RESEARCH_ENV_LOCK = Lock()
_API_KEY_ENV_VAR = "INSIGHT_GRAPH_API_KEY"
_API_KEY_AUTH_ERROR_DETAIL = "Invalid or missing API key."
_JOB_EXECUTOR = ThreadPoolExecutor(max_workers=1)
ResearchJobStatusQuery = Annotated[
    ResearchJobStatus | None,
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
    progress_stage: str | SkipJsonSchema[None] = None
    progress_percent: int | SkipJsonSchema[None] = None
    progress_steps: list[dict[str, str]] | SkipJsonSchema[None] = None
    runtime_seconds: int | SkipJsonSchema[None] = None
    tool_call_count: int | SkipJsonSchema[None] = None
    llm_call_count: int | SkipJsonSchema[None] = None
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
_RESEARCH_JOB_RETRY_CONFLICT_RESPONSE = {
    "description": "Only failed or cancelled research jobs can be retried.",
    "content": {
        "application/json": {
            "example": {"detail": "Only failed or cancelled research jobs can be retried."}
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
_RESEARCH_JOB_REPORT_UNAVAILABLE_RESPONSE = {
    "description": "Research job report is not available.",
    "content": {
        "application/json": {
            "example": {"detail": "Research job report is not available."}
        }
    },
}
_PROGRESS_STEP_LABELS = {
    "planner": "Planner",
    "collector": "Collector",
    "analyst": "Analyst",
    "critic": "Critic",
    "reporter": "Reporter",
}
_PROGRESS_STEP_IDS = tuple(_PROGRESS_STEP_LABELS)


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


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    return HTMLResponse(dashboard_html())


def _current_utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_utc_timestamp(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _add_seconds_to_timestamp(timestamp: str, seconds: int) -> str:
    parsed = _parse_utc_timestamp(timestamp)
    return (parsed + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _elapsed_seconds(started_at: str, finished_at: str) -> int:
    elapsed = _parse_utc_timestamp(finished_at) - _parse_utc_timestamp(started_at)
    return max(0, int(elapsed.total_seconds()))


def _progress_steps(status_by_id: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "id": step_id,
            "label": _PROGRESS_STEP_LABELS[step_id],
            "status": status_by_id.get(step_id, "pending"),
        }
        for step_id in _PROGRESS_STEP_IDS
    ]


def _research_job_progress(job: dict[str, Any]) -> dict[str, Any]:
    status = job["status"]
    result = job.get("result") or {}
    if status == "queued":
        progress_stage = "queued"
        progress_percent = 0
        step_statuses = {step_id: "pending" for step_id in _PROGRESS_STEP_IDS}
    elif status == "running":
        progress_stage = "planner"
        progress_percent = 20
        step_statuses = {"planner": "active"}
    elif status == "succeeded":
        progress_stage = "completed"
        progress_percent = 100
        step_statuses = {step_id: "completed" for step_id in _PROGRESS_STEP_IDS}
    elif status == "failed":
        progress_stage = "failed"
        progress_percent = 100
        step_statuses = {step_id: "skipped" for step_id in _PROGRESS_STEP_IDS}
        step_statuses["planner"] = "failed"
    elif status == "cancelled":
        progress_stage = "cancelled"
        progress_percent = 100
        step_statuses = {step_id: "skipped" for step_id in _PROGRESS_STEP_IDS}
    else:
        progress_stage = status
        progress_percent = 0
        step_statuses = {step_id: "pending" for step_id in _PROGRESS_STEP_IDS}

    runtime_start = job.get("started_at") or job.get("created_at")
    runtime_end = job.get("finished_at")
    runtime_seconds = _elapsed_seconds(runtime_start, runtime_end) if runtime_end else 0
    return {
        "progress_stage": progress_stage,
        "progress_percent": progress_percent,
        "progress_steps": _progress_steps(step_statuses),
        "runtime_seconds": runtime_seconds,
        "tool_call_count": len(result.get("tool_call_log") or []),
        "llm_call_count": len(result.get("llm_call_log") or []),
    }


def _with_research_job_progress(job: dict[str, Any]) -> dict[str, Any]:
    return {**job, **_research_job_progress(job)}


def _lease_expires_at(started_at: str) -> str:
    return _add_seconds_to_timestamp(started_at, RESEARCH_JOB_LEASE_TTL_SECONDS)


def _start_research_job_heartbeat(job_id: str, worker_id: str) -> tuple[Event, Thread | None]:
    stop_event = Event()
    if not using_sqlite_research_jobs_backend():
        return stop_event, None

    def heartbeat_loop() -> None:
        while not stop_event.wait(RESEARCH_JOB_HEARTBEAT_INTERVAL_SECONDS):
            now = _current_utc_timestamp()
            heartbeat_research_job(
                job_id,
                worker_id=worker_id,
                now=now,
                lease_expires_at=_lease_expires_at(now),
            )

    thread = Thread(
        target=heartbeat_loop,
        name=f"research-job-heartbeat-{job_id}",
        daemon=True,
    )
    thread.start()
    return stop_event, thread


def _stop_research_job_heartbeat(stop_event: Event, thread: Thread | None) -> None:
    stop_event.set()
    if thread is not None:
        thread.join(timeout=1)


def _initialize_research_jobs_from_env() -> None:
    configure_research_jobs_backend_from_env()
    initialize_research_jobs(restart_timestamp=_current_utc_timestamp())


_initialize_research_jobs_from_env()


def _configured_api_key() -> str | None:
    api_key = os.environ.get(_API_KEY_ENV_VAR, "").strip()
    return api_key or None


def _candidate_matches_api_key(candidate: str | None, expected: str) -> bool:
    if candidate is None:
        return False
    return hmac.compare_digest(candidate, expected)


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def require_api_key(
    authorization: Annotated[
        str | None,
        Header(alias="Authorization", include_in_schema=False),
    ] = None,
    x_api_key: Annotated[
        str | None,
        Header(alias="X-API-Key", include_in_schema=False),
    ] = None,
) -> None:
    expected_api_key = _configured_api_key()
    if expected_api_key is None:
        return

    candidates = [_bearer_token(authorization), x_api_key]
    if any(_candidate_matches_api_key(candidate, expected_api_key) for candidate in candidates):
        return

    raise HTTPException(status_code=401, detail=_API_KEY_AUTH_ERROR_DETAIL)


_API_KEY_DEPENDENCY = [Depends(require_api_key)]


@router.post("/research", dependencies=_API_KEY_DEPENDENCY)
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
    dependencies=_API_KEY_DEPENDENCY,
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
    response = create_research_job_record(
        query=request.query,
        preset=request.preset,
        created_at=_current_utc_timestamp(),
    )
    _JOB_EXECUTOR.submit(_run_research_job, response["job_id"])
    return response


@router.get(
    "/research/jobs",
    response_model=ResearchJobsListResponse,
    response_model_exclude_none=True,
    dependencies=_API_KEY_DEPENDENCY,
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
    return list_research_job_records(status=status, limit=limit)


@router.get(
    "/research/jobs/summary",
    response_model=ResearchJobsSummaryResponse,
    response_model_exclude_none=True,
    dependencies=_API_KEY_DEPENDENCY,
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
    return summarize_research_jobs_state()


@router.post(
    "/research/jobs/{job_id}/cancel",
    response_model=ResearchJobDetailResponse,
    response_model_exclude_none=True,
    dependencies=_API_KEY_DEPENDENCY,
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
    return cancel_research_job_record(
        job_id=job_id,
        finished_at=_current_utc_timestamp(),
    )


@router.post(
    "/research/jobs/{job_id}/retry",
    status_code=202,
    response_model=ResearchJobCreateResponse,
    response_model_exclude_none=True,
    dependencies=_API_KEY_DEPENDENCY,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Retry failed or cancelled research job",
    description="Create a new queued job from a failed or cancelled research job.",
    responses={
        202: {"content": {"application/json": {"example": _RESEARCH_JOB_CREATE_EXAMPLE}}},
        404: _RESEARCH_JOB_NOT_FOUND_RESPONSE,
        409: _RESEARCH_JOB_RETRY_CONFLICT_RESPONSE,
        429: _TOO_MANY_ACTIVE_RESEARCH_JOBS_RESPONSE,
        500: _RESEARCH_JOB_STORE_FAILED_RESPONSE,
    },
)
def retry_research_job(job_id: str) -> dict[str, str]:
    response = retry_research_job_record(
        job_id=job_id,
        created_at=_current_utc_timestamp(),
    )
    _JOB_EXECUTOR.submit(_run_research_job, response["job_id"])
    return response


def _research_job_report_markdown(job_id: str) -> str:
    job = get_research_job_record(job_id)
    result = job.get("result") or {}
    report_markdown = result.get("report_markdown") if isinstance(result, dict) else None
    if not isinstance(report_markdown, str) or not report_markdown.strip():
        raise HTTPException(
            status_code=409,
            detail="Research job report is not available.",
        )
    return report_markdown


def _markdown_report_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html_lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        "  <title>InsightGraph Research Report</title>",
        "</head>",
        "<body>",
        "<article>",
    ]
    in_list = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue
        if stripped.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{html_escape(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{html_escape(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{html_escape(stripped[4:])}</h3>")
        elif stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{html_escape(stripped[2:])}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{html_escape(stripped)}</p>")
    if in_list:
        html_lines.append("</ul>")
    html_lines.extend(["</article>", "</body>", "</html>"])
    return "\n".join(html_lines) + "\n"


@router.get(
    "/research/jobs/{job_id}/report.md",
    dependencies=_API_KEY_DEPENDENCY,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Download research job Markdown report",
    description="Download the Markdown report for a succeeded research job.",
    responses={
        404: _RESEARCH_JOB_NOT_FOUND_RESPONSE,
        409: _RESEARCH_JOB_REPORT_UNAVAILABLE_RESPONSE,
    },
)
def download_research_job_markdown_report(job_id: str) -> PlainTextResponse:
    return PlainTextResponse(
        _research_job_report_markdown(job_id),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.md"'},
    )


@router.get(
    "/research/jobs/{job_id}/report.html",
    response_class=HTMLResponse,
    dependencies=_API_KEY_DEPENDENCY,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Download research job HTML report",
    description="Download an escaped HTML rendering for a succeeded research job report.",
    responses={
        404: _RESEARCH_JOB_NOT_FOUND_RESPONSE,
        409: _RESEARCH_JOB_REPORT_UNAVAILABLE_RESPONSE,
    },
)
def download_research_job_html_report(job_id: str) -> HTMLResponse:
    return HTMLResponse(
        _markdown_report_to_html(_research_job_report_markdown(job_id)),
        headers={"Content-Disposition": f'attachment; filename="{job_id}.html"'},
    )


@router.get(
    "/research/jobs/{job_id}",
    response_model=ResearchJobDetailResponse,
    response_model_exclude_none=True,
    dependencies=_API_KEY_DEPENDENCY,
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
    return _with_research_job_progress(get_research_job_record(job_id))


def _run_research_job(job_id: str) -> None:
    worker_id = research_jobs_worker_id()
    job = mark_research_job_running(
        job_id=job_id,
        started_at=_current_utc_timestamp,
        store_failure_finished_at=_current_utc_timestamp,
        worker_id=worker_id,
        lease_expires_at=_lease_expires_at,
    )
    if job is None:
        return

    stop_event, heartbeat_thread = _start_research_job_heartbeat(job.id, worker_id)
    try:
        try:
            with _RESEARCH_ENV_LOCK:
                with _research_preset_environment(job.preset):
                    state = run_research(job.query)
            result = _build_research_json_payload(state)
        except Exception:
            mark_research_job_failed(
                job,
                finished_at=_current_utc_timestamp(),
                error="Research workflow failed.",
                worker_id=worker_id,
            )
            return

        mark_research_job_succeeded(
            job,
            finished_at=_current_utc_timestamp(),
            result=result,
            worker_id=worker_id,
        )
    finally:
        _stop_research_job_heartbeat(stop_event, heartbeat_thread)


app = create_app()
