# Research Job Repository Split Design

## Goal

Move research job state management out of `src/insight_graph/api.py` into one focused repository module without changing runtime behavior.

## Scope

Create `src/insight_graph/research_jobs.py` as the in-process research job repository boundary. Move job state, persistence integration, response builders, queue/summary helpers, pruning, and worker state-transition helpers into that module.

Keep FastAPI routes in `src/insight_graph/api.py`. The routes should remain responsible for HTTP wiring, OpenAPI metadata, request/response models, and invoking the research workflow. The repository should own in-memory job state and JSON persistence interactions.

## Current Problem

`src/insight_graph/api.py` now mixes several responsibilities:

- FastAPI app/router setup
- request/response model declarations
- OpenAPI examples and operation metadata
- `/research` workflow execution
- research job dataclass and status constants
- in-memory job dictionary, sequence counter, and locks
- JSON store loading/saving and rollback snapshots
- job response builders
- queue positions and summary calculations
- worker status transitions and terminal pruning

This makes `api.py` harder to scan and raises the cost of later storage evolution. A repository boundary will make the current in-process implementation easier to reason about while preserving all endpoint behavior.

## Design

### New Module

Add `src/insight_graph/research_jobs.py`.

This module owns:

- `ResearchJob`
- status constants:
  - `RESEARCH_JOB_STATUS_QUEUED`
  - `RESEARCH_JOB_STATUS_RUNNING`
  - `RESEARCH_JOB_STATUS_SUCCEEDED`
  - `RESEARCH_JOB_STATUS_FAILED`
  - `RESEARCH_JOB_STATUS_CANCELLED`
  - `RESEARCH_JOB_STATUSES`
  - `ACTIVE_RESEARCH_JOB_STATUSES`
  - `TERMINAL_RESEARCH_JOB_STATUSES`
- retained and active limits
- job lock, job dictionary, and next sequence counter
- configured JSON store path
- initialization from configured store
- persistence and HTTP-safe store failure conversion
- rollback snapshots
- job create/cancel/list/detail/summary helpers
- worker state transition helpers
- terminal pruning

The module may use leading-underscore names internally. Public functions imported by `api.py` should avoid leading underscores.

### API Module Responsibilities

`src/insight_graph/api.py` keeps:

- FastAPI `router`, `create_app()`, and module-level `app`
- `_RESEARCH_ENV_LOCK`
- `_JOB_EXECUTOR`
- `ResearchRequest` and response model classes
- OpenAPI metadata constants and route decorators
- `/research` route
- worker orchestration around `run_research()` and `_build_research_json_payload()`

`api.py` should call repository functions for job lifecycle operations:

- create queued job
- list jobs
- summarize jobs
- cancel job
- get job detail
- mark worker running
- mark worker failed
- mark worker succeeded

### Suggested Repository API

Use these public functions unless implementation finds a smaller equivalent set:

- `initialize_research_jobs() -> None`
- `create_research_job(query: str, preset: ResearchPreset, created_at: str) -> dict[str, str]`
- `list_research_jobs(status: ResearchJobStatus | None, limit: int) -> dict[str, Any]`
- `summarize_research_jobs() -> dict[str, Any]`
- `cancel_research_job(job_id: str, finished_at: str) -> dict[str, Any]`
- `get_research_job(job_id: str) -> dict[str, Any]`
- `mark_research_job_running(job_id: str, started_at: str) -> ResearchJob | None`
- `mark_research_job_failed(job: ResearchJob, finished_at: str, error: str) -> None`
- `mark_research_job_succeeded(job: ResearchJob, finished_at: str, result: dict[str, Any]) -> None`

`mark_research_job_running()` returns `None` when the job was cancelled or when storing the running transition fails. It returns the `ResearchJob` when workflow execution should proceed.

### Timestamps

Keep timestamp creation in `api.py` via `_current_utc_timestamp()` for now. Pass timestamps into repository functions. This keeps the repository deterministic and easier to test without monkeypatching time inside the repository module.

### HTTP Errors

The repository may raise FastAPI `HTTPException` for current HTTP-facing failures:

- `404`: `Research job not found.`
- `409`: `Only queued research jobs can be cancelled.`
- `429`: `Too many active research jobs.`
- `500`: `Research job store failed.`

This keeps route code thin and preserves current response bodies.

### Test Migration

Add `tests/test_research_jobs.py` for repository behavior currently tested through `api_module` internals. Keep HTTP/route/OpenAPI tests in `tests/test_api.py`.

Move or add focused repository tests for:

- status constants
- initialize no-op without configured store path
- initialize from configured store
- initialize fail-closed for bad store
- snapshot restore behavior if still explicit
- create store write rollback
- cancel store write rollback
- running transition store failure
- terminal store failure best-effort
- terminal pruning
- list/detail/summary response builder behavior

`tests/test_api.py` should stop reaching into repository internals except where route tests need controlled job state. For route tests that need controlled state, prefer repository setup helpers or direct imports from `insight_graph.research_jobs`.

## Compatibility

Do not add compatibility aliases in `api.py` for old private names such as `_JOBS`, `_NEXT_JOB_SEQUENCE`, `_JOBS_LOCK`, or `_persist_research_jobs_locked`. Tests should migrate to the new module. These names were private internals, not public API.

## Non-Goals

- No endpoint changes.
- No response JSON changes.
- No OpenAPI metadata changes beyond import fallout.
- No persistence schema changes.
- No SQLite/Postgres backend.
- No multi-process coordination.
- No worker pool changes.
- No retry/resume behavior.
- No auth changes.

## Testing

Run:

```bash
python -m pytest tests/test_research_jobs.py -q
python -m pytest tests/test_api.py -q
python -m pytest -q
python -m ruff check .
```

The full suite should keep the existing skipped test count unchanged.

## Self-Review

- Scope is one repository module, not multi-module cleanup.
- Runtime behavior stays unchanged.
- Private API compatibility aliases are explicitly out of scope.
- Store schema stays unchanged.
- Worker execution semantics stay unchanged.
- No placeholders remain.
