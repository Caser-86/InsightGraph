# Research Job Manual Retry Design

## Goal

Add a safe manual retry path for terminal failed or cancelled research jobs without changing automatic startup behavior or adding worker leasing.

## Scope

- Add `POST /research/jobs/{job_id}/retry`.
- Retry creates a new queued job using the original job's `query` and `preset`.
- The original job remains unchanged for history and debugging.
- The new job follows the same queue, active-cap, worker scheduling, persistence, and response behavior as normal job creation.
- Support both in-memory and SQLite backends through the service layer.

## Non-goals

- No automatic retry.
- No automatic resume of `queued` or `running` jobs after restart.
- No worker leasing or multi-process coordination.
- No attempt counters or lineage fields in this first pass.
- No retry of succeeded jobs.

## API Behavior

Endpoint:

```http
POST /research/jobs/{job_id}/retry
```

Success response:

- Status: `202 Accepted`.
- Body: same shape as job create response: `job_id`, `status`, `created_at`.
- Returned `job_id` is a new job ID.
- Returned `status` is `queued`.

Failure responses:

- `404` when the source job does not exist.
- `409` when source job status is not `failed` or `cancelled`.
- `429` when active job cap is reached.
- `500` when configured storage fails during retry creation.

## Service Behavior

- Add a service helper such as `retry_research_job(job_id, created_at)`.
- The helper reads the source job through the backend/service access layer.
- The helper validates status in `failed` or `cancelled`.
- The helper calls existing job creation logic with source `query` and `preset`.
- The helper never copies `result`, `error`, `started_at`, `finished_at`, or `created_order` from the source job.

## Backend Behavior

- No new persisted fields are required.
- Existing create/list/detail/summary/cancel behavior remains unchanged.
- Existing active-cap and terminal-pruning semantics apply to the new job.
- SQLite and memory backends need no schema change.

## Worker Behavior

- API endpoint schedules the newly created job exactly like `POST /research/jobs`.
- If scheduling fails before response, behavior should match current create endpoint assumptions; no additional rollback semantics are added.
- If worker execution fails, new job becomes `failed` with safe error `Research workflow failed.`.

## Testing Requirements

- Service test: retry failed job creates a distinct queued job with same query/preset.
- Service test: retry cancelled job creates a distinct queued job.
- Service test: retry missing job returns 404 through API helper behavior.
- Service test: retry queued/running/succeeded job returns 409.
- API test: retry endpoint returns 202 and schedules the new job.
- API test: active cap still returns 429.
- Backend contract test: memory and SQLite backends both support retry through public service helper.

## Documentation

- Update `docs/research-jobs-api.md` with retry endpoint, status codes, and examples.
- Update `docs/research-job-repository-contract.md` to state manual retry creates a new job and leaves source job unchanged.
