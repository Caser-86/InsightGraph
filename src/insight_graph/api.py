import asyncio
import hmac
import os
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from html import escape as html_escape
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, field_validator
from pydantic.json_schema import SkipJsonSchema

from insight_graph.cli import (
    LIVE_LLM_PRESET_DEFAULTS,
    LIVE_RESEARCH_PRESET_DEFAULTS,
    ResearchPreset,
    _build_research_json_payload,
)
from insight_graph.dashboard import dashboard_html
from insight_graph.graph import run_research, run_research_with_events
from insight_graph.memory.embeddings import embed_text
from insight_graph.memory.store import ResearchMemoryRecord, get_research_memory_store
from insight_graph.persistence.checkpoints import get_checkpoint_store
from insight_graph.research_jobs import (
    RESEARCH_JOB_HEARTBEAT_INTERVAL_SECONDS,
    RESEARCH_JOB_LEASE_TTL_SECONDS,
    ResearchJobStatus,
    append_research_job_event,
    claim_next_research_job_for_worker,
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
from insight_graph.state import GraphState

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
_RESEARCH_JOB_STREAM_INTERVAL_SECONDS = 1.0
_RESEARCH_JOB_EVENT_LIMIT = 100
_RESEARCH_JOB_EVENTS: dict[str, list[dict[str, Any]]] = {}
_RESEARCH_JOB_EVENT_SUBSCRIBERS: dict[str, list[Queue[dict[str, Any]]]] = {}
_RESEARCH_JOB_EVENT_LOCK = Lock()
_DEFAULT_RUN_RESEARCH = run_research
_CHECKPOINT_RESUME_ENV_VAR = "INSIGHT_GRAPH_CHECKPOINT_RESUME"
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
    events: list[dict[str, Any]] | SkipJsonSchema[None] = None
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


class MemoryRecordResponse(BaseModel):
    memory_id: str
    text: str
    metadata: dict[str, Any]


class MemoryListResponse(BaseModel):
    records: list[MemoryRecordResponse]
    count: int


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 5
    metadata_filter: dict[str, object] | None = None


class MemoryDeleteResponse(BaseModel):
    deleted: bool


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
_PROGRESS_STAGE_PERCENT = {
    "planner": 20,
    "collector": 40,
    "analyst": 60,
    "critic": 80,
    "reporter": 95,
}


@contextmanager
def _research_preset_environment(preset: ResearchPreset) -> Iterator[None]:
    if preset == ResearchPreset.offline:
        yield
        return

    defaults = (
        LIVE_RESEARCH_PRESET_DEFAULTS
        if preset == ResearchPreset.live_research
        else LIVE_LLM_PRESET_DEFAULTS
    )
    previous_values = {name: os.environ.get(name) for name in defaults}
    try:
        for name, value in defaults.items():
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


def _stage_progress_from_events(
    job_id: str | None,
    status: str,
) -> dict[str, Any] | None:
    if job_id is None:
        return None

    active_stage: str | None = None
    last_started_stage: str | None = None
    finished_stages: set[str] = set()
    for event in _cached_research_job_events(job_id):
        stage = event.get("stage")
        if stage not in _PROGRESS_STEP_IDS:
            continue
        if event.get("type") == "stage_started":
            active_stage = stage
            last_started_stage = stage
        elif event.get("type") == "stage_finished":
            finished_stages.add(stage)
            if active_stage == stage:
                active_stage = None

    if last_started_stage is None:
        return None

    if status == "failed":
        failed_stage = active_stage or last_started_stage
        failed_index = _PROGRESS_STEP_IDS.index(failed_stage)
        step_statuses = {
            step_id: _failed_stage_step_status(index, failed_index)
            for index, step_id in enumerate(_PROGRESS_STEP_IDS)
        }
        return {
            "progress_stage": "failed",
            "progress_percent": 100,
            "progress_steps": _progress_steps(step_statuses),
        }

    current_stage = active_stage or _next_active_stage(finished_stages)
    current_index = _PROGRESS_STEP_IDS.index(current_stage)
    step_statuses = {
        step_id: _running_stage_step_status(index, current_index)
        for index, step_id in enumerate(_PROGRESS_STEP_IDS)
    }
    return {
        "progress_stage": current_stage,
        "progress_percent": _PROGRESS_STAGE_PERCENT[current_stage],
        "progress_steps": _progress_steps(step_statuses),
    }


def _next_active_stage(finished_stages: set[str]) -> str:
    for step_id in _PROGRESS_STEP_IDS:
        if step_id not in finished_stages:
            return step_id
    return "reporter"


def _running_stage_step_status(index: int, current_index: int) -> str:
    if index < current_index:
        return "completed"
    if index == current_index:
        return "active"
    return "pending"


def _failed_stage_step_status(index: int, failed_index: int) -> str:
    if index < failed_index:
        return "completed"
    if index == failed_index:
        return "failed"
    return "skipped"


def _research_job_progress(job: dict[str, Any]) -> dict[str, Any]:
    status = job["status"]
    result = job.get("result") or {}
    if status == "queued":
        progress_stage = "queued"
        progress_percent = 0
        step_statuses = {step_id: "pending" for step_id in _PROGRESS_STEP_IDS}
        progress_steps = _progress_steps(step_statuses)
    elif status == "running":
        event_progress = _stage_progress_from_events(job.get("job_id"), status)
        if event_progress is not None:
            progress_stage = event_progress["progress_stage"]
            progress_percent = event_progress["progress_percent"]
            progress_steps = event_progress["progress_steps"]
        else:
            progress_stage = "planner"
            progress_percent = 20
            step_statuses = {"planner": "active"}
            progress_steps = _progress_steps(step_statuses)
    elif status == "succeeded":
        progress_stage = "completed"
        progress_percent = 100
        step_statuses = {step_id: "completed" for step_id in _PROGRESS_STEP_IDS}
        progress_steps = _progress_steps(step_statuses)
    elif status == "failed":
        event_progress = _stage_progress_from_events(job.get("job_id"), status)
        progress_stage = "failed"
        progress_percent = 100
        if event_progress is not None:
            progress_steps = event_progress["progress_steps"]
        else:
            step_statuses = {step_id: "skipped" for step_id in _PROGRESS_STEP_IDS}
            step_statuses["planner"] = "failed"
            progress_steps = _progress_steps(step_statuses)
    elif status == "cancelled":
        progress_stage = "cancelled"
        progress_percent = 100
        step_statuses = {step_id: "skipped" for step_id in _PROGRESS_STEP_IDS}
        progress_steps = _progress_steps(step_statuses)
    else:
        progress_stage = status
        progress_percent = 0
        step_statuses = {step_id: "pending" for step_id in _PROGRESS_STEP_IDS}
        progress_steps = _progress_steps(step_statuses)

    runtime_start = job.get("started_at") or job.get("created_at")
    runtime_end = job.get("finished_at")
    runtime_seconds = _elapsed_seconds(runtime_start, runtime_end) if runtime_end else 0
    return {
        "progress_stage": progress_stage,
        "progress_percent": progress_percent,
        "progress_steps": progress_steps,
        "runtime_seconds": runtime_seconds,
        "tool_call_count": len(result.get("tool_call_log") or []),
        "llm_call_count": len(result.get("llm_call_log") or []),
    }


def _with_research_job_progress(job: dict[str, Any]) -> dict[str, Any]:
    return {**job, **_research_job_progress(job)}


def _clear_research_job_events(job_id: str) -> None:
    with _RESEARCH_JOB_EVENT_LOCK:
        _RESEARCH_JOB_EVENTS.pop(job_id, None)
        for subscriber in _RESEARCH_JOB_EVENT_SUBSCRIBERS.pop(job_id, []):
            subscriber.put({"type": "stream_closed"})


def _publish_research_job_event(job_id: str, event: dict[str, Any]) -> dict[str, Any]:
    with _RESEARCH_JOB_EVENT_LOCK:
        events = _RESEARCH_JOB_EVENTS.setdefault(job_id, [])
        event_with_sequence = {**event, "sequence": _next_research_job_event_sequence(job_id)}
        events.append(event_with_sequence)
        del events[:-_RESEARCH_JOB_EVENT_LIMIT]
        for subscriber in _RESEARCH_JOB_EVENT_SUBSCRIBERS.get(job_id, []):
            subscriber.put(event_with_sequence)
    append_research_job_event(
        job_id,
        event_with_sequence,
        limit=_RESEARCH_JOB_EVENT_LIMIT,
    )
    return event_with_sequence


def _next_research_job_event_sequence(job_id: str) -> int:
    sequences = [
        event.get("sequence")
        for event in [
            *_RESEARCH_JOB_EVENTS.get(job_id, []),
            *_persisted_research_job_events(job_id),
        ]
    ]
    return max((value for value in sequences if isinstance(value, int)), default=0) + 1


def _persisted_research_job_events(job_id: str) -> list[dict[str, Any]]:
    try:
        job = get_research_job_record(job_id)
    except HTTPException:
        return []
    events = job.get("events")
    if not isinstance(events, list):
        return []
    return [dict(event) for event in events if isinstance(event, dict)]


def _cached_research_job_events(job_id: str) -> list[dict[str, Any]]:
    with _RESEARCH_JOB_EVENT_LOCK:
        events = [dict(event) for event in _RESEARCH_JOB_EVENTS.get(job_id, [])]
    if events:
        return events
    return _persisted_research_job_events(job_id)


def _subscribe_research_job_events(job_id: str) -> Queue[dict[str, Any]]:
    queue: Queue[dict[str, Any]] = Queue()
    with _RESEARCH_JOB_EVENT_LOCK:
        _RESEARCH_JOB_EVENT_SUBSCRIBERS.setdefault(job_id, []).append(queue)
    return queue


def _unsubscribe_research_job_events(job_id: str, queue: Queue[dict[str, Any]]) -> None:
    with _RESEARCH_JOB_EVENT_LOCK:
        subscribers = _RESEARCH_JOB_EVENT_SUBSCRIBERS.get(job_id)
        if subscribers is None:
            return
        if queue in subscribers:
            subscribers.remove(queue)
        if not subscribers:
            _RESEARCH_JOB_EVENT_SUBSCRIBERS.pop(job_id, None)


def _next_research_job_event(
    queue: Queue[dict[str, Any]],
    timeout_seconds: float,
) -> dict[str, Any] | None:
    try:
        return queue.get(timeout=timeout_seconds)
    except Empty:
        return None


def _run_research_job_workflow(
    query: str,
    emit_event: Callable[[dict[str, Any]], None],
    *,
    job_id: str | None = None,
) -> GraphState:
    if run_research is not _DEFAULT_RUN_RESEARCH:
        return run_research(query)
    if job_id is not None and _checkpoint_resume_enabled():
        return run_research_with_events(
            query,
            emit_event,
            run_id=job_id,
            checkpoint_store=get_checkpoint_store(),
            resume=True,
        )
    return run_research_with_events(query, emit_event)


def _checkpoint_resume_enabled() -> bool:
    return os.environ.get(_CHECKPOINT_RESUME_ENV_VAR, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


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
    _submit_startup_research_jobs()


def _startup_worker_enabled() -> bool:
    return os.environ.get("INSIGHT_GRAPH_RESEARCH_JOBS_STARTUP_WORKER", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _submit_startup_research_jobs() -> None:
    if not _startup_worker_enabled() or not using_sqlite_research_jobs_backend():
        return
    while True:
        job = claim_next_research_job_for_worker(
            started_at=_current_utc_timestamp,
            worker_id=research_jobs_worker_id(),
            lease_expires_at=_lease_expires_at,
        )
        if job is None:
            return
        _JOB_EXECUTOR.submit(_run_claimed_research_job, job, research_jobs_worker_id())


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


def _api_key_is_authorized(*candidates: str | None) -> bool:
    expected_api_key = _configured_api_key()
    if expected_api_key is None:
        return True
    return any(_candidate_matches_api_key(candidate, expected_api_key) for candidate in candidates)


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
    if _api_key_is_authorized(_bearer_token(authorization), x_api_key):
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


def _memory_record_response(record: ResearchMemoryRecord) -> dict[str, Any]:
    return {
        "memory_id": record.memory_id,
        "text": record.text,
        "metadata": record.metadata,
    }


@router.get(
    "/memory",
    response_model=MemoryListResponse,
    dependencies=_API_KEY_DEPENDENCY,
    tags=["memory"],
)
def list_memory_records(limit: int = 100) -> dict[str, Any]:
    store = get_research_memory_store()
    store.ensure_schema()
    records = store.list_memories(limit=limit)
    return {
        "records": [_memory_record_response(record) for record in records],
        "count": len(records),
    }


@router.post(
    "/memory/search",
    response_model=MemoryListResponse,
    dependencies=_API_KEY_DEPENDENCY,
    tags=["memory"],
)
def search_memory_records(request: MemorySearchRequest) -> dict[str, Any]:
    store = get_research_memory_store()
    store.ensure_schema()
    records = store.search(
        embed_text(request.query),
        limit=request.limit,
        metadata_filter=request.metadata_filter,
    )
    return {
        "records": [_memory_record_response(record) for record in records],
        "count": len(records),
    }


@router.delete(
    "/memory/{memory_id}",
    response_model=MemoryDeleteResponse,
    dependencies=_API_KEY_DEPENDENCY,
    tags=["memory"],
)
def delete_memory_record(memory_id: str) -> dict[str, bool]:
    store = get_research_memory_store()
    store.ensure_schema()
    return {"deleted": store.delete_memory(memory_id)}


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


async def _send_research_job_stream_event(websocket: WebSocket, job_id: str) -> bool:
    try:
        job = _with_research_job_progress(get_research_job_record(job_id))
    except HTTPException as exc:
        await websocket.send_json({"type": "error", "detail": exc.detail})
        return True

    await websocket.send_json({"type": "job_snapshot", "job": job})
    return job["status"] in {"succeeded", "failed", "cancelled"}


async def _send_cached_research_job_events(websocket: WebSocket, job_id: str) -> None:
    for event in _cached_research_job_events(job_id):
        await websocket.send_json(event)


@router.websocket("/research/jobs/{job_id}/stream")
async def stream_research_job(
    websocket: WebSocket,
    job_id: str,
    api_key: str | None = None,
) -> None:
    if not _api_key_is_authorized(api_key):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    await websocket.accept()
    terminal = await _send_research_job_stream_event(websocket, job_id)
    await _send_cached_research_job_events(websocket, job_id)
    if terminal:
        await websocket.close()
        return

    event_queue = _subscribe_research_job_events(job_id)
    try:
        while True:
            event = await asyncio.to_thread(
                _next_research_job_event,
                event_queue,
                _RESEARCH_JOB_STREAM_INTERVAL_SECONDS,
            )
            if event is not None and event["type"] != "stream_closed":
                await websocket.send_json(event)
            terminal = await _send_research_job_stream_event(websocket, job_id)
            if terminal:
                await websocket.close()
                return
    except WebSocketDisconnect:
        return
    finally:
        _unsubscribe_research_job_events(job_id, event_queue)


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
    _clear_research_job_events(job_id)
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
                    state = _run_research_job_workflow(
                        job.query,
                        lambda event: _publish_research_job_event(job.id, event),
                        job_id=job.id,
                    )
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


def _run_claimed_research_job(job, worker_id: str) -> None:
    _clear_research_job_events(job.id)
    stop_event, heartbeat_thread = _start_research_job_heartbeat(job.id, worker_id)
    try:
        try:
            with _RESEARCH_ENV_LOCK:
                with _research_preset_environment(job.preset):
                    state = _run_research_job_workflow(
                        job.query,
                        lambda event: _publish_research_job_event(job.id, event),
                        job_id=job.id,
                    )
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
