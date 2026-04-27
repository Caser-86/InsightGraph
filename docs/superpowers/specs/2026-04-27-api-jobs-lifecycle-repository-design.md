# API Jobs Lifecycle And Repository Cleanup Design

## Goal

Make the research jobs API easier to test and evolve by separating app initialization and job state operations from endpoint handlers, without changing public API response shapes or JSON persistence semantics.

## Scope

This change is an internal structure cleanup for the existing FastAPI research jobs MVP. It may move logic into small helpers, but it must not change endpoint paths, status codes, response bodies, OpenAPI response models, JSON store format, active-limit behavior, retention behavior, cancellation rules, or restart recovery policy.

## Combined Tasks

This batch intentionally combines three tightly related tasks:

- API app factory / lifecycle cleanup
- Research job repository boundary
- Job store reload/startup tests

It explicitly does not include broader worker policy changes or OpenAPI polish.

## App Lifecycle

Add a `create_app()` function that returns a configured `FastAPI` instance. Keep the existing module-level `app` by assigning `app = create_app()` so current imports and CLI/server usage keep working.

Add an explicit initialization boundary for research jobs. Tests should be able to call this initializer directly with a configured path and timestamp provider instead of relying on module import side effects.

The existing behavior remains:

- If `INSIGHT_GRAPH_RESEARCH_JOBS_PATH` is unset, jobs are in memory only.
- If set, jobs are loaded from the JSON store at startup/import initialization.
- Malformed configured stores fail closed.
- Restored `queued` and `running` jobs become failed restart records.

## Repository Boundary

Add a small in-process repository/helper object or module-level helper group responsible for `_JOBS`, `_NEXT_JOB_SEQUENCE`, active counts, retention pruning, queue positions, and persistence rollback snapshots.

The repository boundary should keep the current concurrency model: one process, one `threading.Lock`, one `ThreadPoolExecutor(max_workers=1)`. It should not introduce async code, database dependencies, or cross-process file locking.

Endpoint handlers should continue to own HTTP concerns:

- request validation
- HTTP errors
- response model decorators
- executor submission

The repository/helper layer should own state mutation primitives:

- create queued job
- cancel queued job
- mark running
- mark succeeded
- mark failed
- list/detail/summary data retrieval
- load/save persistence state

## Persistence Semantics

Keep `src/insight_graph/research_jobs_store.py` as the JSON serialization layer. The cleanup may adjust how `api.py` calls it, but the stored JSON schema remains unchanged:

- `next_job_sequence`
- `jobs`
- job fields `id`, `query`, `preset`, `created_order`, `created_at`, `status`, `started_at`, `finished_at`, `result`, `error`

Queue positions remain dynamic and are not stored.

Write failures during mutating requests must continue to return safe `500` detail `Research job store failed.` and roll back in-memory state for create/cancel mutations.

Background persistence failures must not leave jobs in active statuses indefinitely.

## Testing

Add or update tests for:

- `create_app()` returns an app with the current routes.
- Module-level `app` remains available and compatible.
- Explicit job initialization loads a configured JSON store.
- Explicit job initialization is a no-op when path is unset.
- Bad configured JSON still fails closed.
- Existing public response shape tests continue to pass.
- Existing JSON persistence failure rollback tests continue to pass.
- Tests no longer need to depend on import-time store loading for persistence behavior.

Run focused API/store tests, full pytest, and ruff.

## Non-Goals

- No worker pool changes.
- No retry policy changes.
- No automatic resume of unfinished jobs.
- No endpoint path or response shape changes.
- No new persistence backend.
- No database migrations.
- No OpenAPI description/example polish in this batch.

## Self-Review

- No placeholders remain.
- Scope is limited to lifecycle and state boundary cleanup.
- Public API compatibility is explicit.
- Persistence behavior and failure semantics are preserved.
