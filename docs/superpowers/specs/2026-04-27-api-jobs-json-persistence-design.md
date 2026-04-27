# API Jobs JSON Persistence Design

## Goal

Add an opt-in durable JSON store for research job metadata so job records can survive API process restarts without changing the public jobs API shape.

## Scope

This change only persists the current research jobs registry and sequence counter. It does not persist LangGraph checkpoints, rerun unfinished research work after restart, add authentication, add WebSockets, or introduce a database dependency.

## Configuration

Persistence is disabled by default. Existing behavior remains a pure in-memory job store unless this environment variable is set:

- `INSIGHT_GRAPH_RESEARCH_JOBS_PATH=/path/to/jobs.json`

When the variable is set, the API loads jobs from that file during module initialization and writes the file after mutating job state.

## Stored Data

The JSON file stores:

- `next_job_sequence`: integer value used to assign future `created_order` values.
- `jobs`: list of serialized research jobs.

Each serialized job stores:

- `id`
- `query`
- `preset`
- `created_order`
- `created_at`
- `status`
- `started_at`
- `finished_at`
- `result`
- `error`

The file intentionally does not store queue positions. Queue positions remain dynamic values computed from the current queued set.

## Restart Recovery

Terminal jobs restore as-is:

- `succeeded`
- `failed`
- `cancelled`

Non-terminal jobs do not resume automatically. During load, jobs with `queued` or `running` status are converted to `failed` with:

- `error`: `Research job did not complete before server restart.`
- `finished_at`: current UTC timestamp from the API timestamp provider

This avoids duplicate research execution after a process restart. The executor is not populated from restored jobs.

## Write Semantics

When persistence is enabled, the API writes the JSON store after these state changes:

- creating a job
- cancelling a job
- marking a job `running`
- marking a job `succeeded`
- marking a job `failed`
- pruning terminal jobs

Writes are atomic: serialize to a temporary file in the same directory, then replace the target file. JSON output is readable with `indent=2` and `sort_keys=True`.

If writing fails during a mutating request, the request returns safe HTTP `500` detail `Research job store failed.` and does not expose local paths or raw exception payloads.

If loading fails because the configured JSON file is malformed or has an invalid schema, import/startup fails instead of silently dropping persisted jobs.

## Module Boundaries

Add `src/insight_graph/research_jobs_store.py` for storage concerns:

- serializing `ResearchJob` values
- deserializing jobs from JSON objects
- applying restart recovery policy
- loading from disk
- atomically saving to disk

Keep FastAPI endpoints, locks, executor submission, response builders, retention, active-limit checks, and queue-position calculation in `src/insight_graph/api.py`.

The store module may use standard library modules only. No SQLite, PostgreSQL, SQLAlchemy, or migration framework is included in this step.

## Testing

Add tests for:

- Default unset environment does not read or write a jobs file.
- JSON save and load round-trip terminal jobs and `next_job_sequence`.
- Loading `queued` and `running` jobs converts them to failed restart records.
- Malformed JSON load raises an exception.
- Creating a job writes the configured JSON file.
- Completing or failing a job updates the configured JSON file.
- Cancelling and pruning jobs update the configured JSON file.
- Write failure during a mutating API request returns safe `500` detail.
- Public jobs API response shapes remain unchanged.

Run focused store/API tests, full pytest, and ruff.

## Non-Goals

- No automatic resume or retry of unfinished jobs.
- No database-backed store.
- No migration system.
- No multi-process coordination.
- No file locking across processes.
- No auth, WebSocket, or streaming behavior.
- No change to existing job response models.

## Self-Review

- No placeholders remain.
- The design is limited to optional JSON persistence for the existing jobs MVP.
- Restart behavior is explicit and avoids duplicate execution.
- Failure handling is explicit for both load and write failures.
- Public API response shapes remain unchanged.
