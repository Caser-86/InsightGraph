# SQLite Research Job Worker Leasing Design

## Goal

Add SQLite-only worker leasing for research jobs so multiple API processes can coordinate background execution without double-starting the same job. Expired running jobs are requeued for another worker to claim.

## Scope

- SQLite backend only.
- Public API response shapes remain unchanged.
- Existing in-memory backend behavior remains unchanged.
- Expired `running` jobs requeue instead of failing.
- Default lease TTL is 300 seconds.
- Default heartbeat interval is 60 seconds.

## Non-goals

- No running-job cancellation endpoint.
- No public lease metadata fields.
- No distributed worker service outside the existing process executor.
- No Postgres implementation.
- No in-memory lease simulation.

## Recommended Approach

Use lease columns on `research_jobs`.

Add internal SQLite fields:

- `worker_id TEXT`
- `lease_expires_at TEXT`
- `heartbeat_at TEXT`
- `attempt_count INTEGER NOT NULL DEFAULT 0`

This keeps lease state in the same row as job state, avoids joins, and lets claim, reclaim, heartbeat, and terminal writes use simple transactional updates.

## Worker Identity

Each API process gets one generated `worker_id` at startup. The ID is used only for internal SQLite lease ownership checks.

The worker ID does not need to be stable across process restarts. If a process dies, its running jobs become reclaimable when `lease_expires_at` passes.

## Claim Semantics

SQLite job execution must claim a job before running the workflow.

In one `BEGIN IMMEDIATE` transaction:

1. Requeue expired `running` jobs whose `lease_expires_at` is older than `now`.
2. Select the requested job ID.
3. Return no job if it is missing, terminal, cancelled, or actively leased by another worker.
4. If the job is `queued`, update it to `running`.
5. Set `worker_id`, `heartbeat_at`, and `lease_expires_at`.
6. Increment `attempt_count`.
7. Set `started_at` only if it was not already set.
8. Commit and return the claimed job.

The service layer should treat a missing claim as "do not run workflow".

## Heartbeat Semantics

While a SQLite-backed workflow runs, a heartbeat refreshes the lease every 60 seconds.

Heartbeat update rule:

- Update only if `id`, `worker_id`, and `status = 'running'` match.
- Set `heartbeat_at = now`.
- Set `lease_expires_at = now + 300 seconds`.
- Return whether a row was updated.

If heartbeat cannot update the row, the worker may continue local execution, but it no longer owns the lease. Its final terminal write must not overwrite the current job state unless ownership is still valid.

## Reclaim Semantics

Expired running jobs are requeued before claim attempts.

Requeue update rule:

- Match `status = 'running'` and `lease_expires_at < now`.
- Set `status = 'queued'`.
- Clear `worker_id`, `lease_expires_at`, and `heartbeat_at`.
- Keep `started_at` and `attempt_count` for observability.
- Keep `result` and `error` empty because the job is active again.

This makes abandoned jobs retryable by normal queue execution without exposing a separate failure state.

## Terminal Update Semantics

SQLite terminal writes must be ownership-aware.

Terminal update rule:

- Update only if `id`, `worker_id`, and `status = 'running'` match.
- Set terminal status, `finished_at`, result or safe error.
- Clear `worker_id`, `lease_expires_at`, and `heartbeat_at`.
- Prune old terminal jobs after the terminal update.

If no row is updated, the worker lost ownership. The stale terminal result is ignored.

Provider exceptions still use the existing safe failed-job error policy. Lease loss must not expose provider details.

## API Behavior

No public API response fields change.

- `POST /research/jobs` still returns `202` with the new job ID.
- `POST /research/jobs/{job_id}/retry` still creates a new queued job from failed or cancelled jobs.
- `GET /research/jobs` and `GET /research/jobs/{job_id}` still expose current job lifecycle fields only.
- `POST /research/jobs/{job_id}/cancel` remains queued-only.

Internal reclaim may make an abandoned `running` job appear as `queued` again. Queue position is still derived dynamically.

## Storage Migration

Existing SQLite databases must upgrade in place.

On initialization, after `CREATE TABLE IF NOT EXISTS`, inspect columns with `PRAGMA table_info(research_jobs)` and add missing lease columns with `ALTER TABLE`.

Required migrations:

- Add nullable `worker_id`.
- Add nullable `lease_expires_at`.
- Add nullable `heartbeat_at`.
- Add `attempt_count INTEGER NOT NULL DEFAULT 0`.

New databases include the columns in `SCHEMA`; old databases get the same final shape through migration.

## Configuration

Use internal constants for initial implementation:

- `RESEARCH_JOB_LEASE_TTL_SECONDS = 300`
- `RESEARCH_JOB_HEARTBEAT_INTERVAL_SECONDS = 60`

Environment overrides are out of scope for this change. Add them later only if operational use shows the defaults are wrong.

## Error Handling

- Claim failures return `None` to the service layer and do not run work.
- Heartbeat failures do not immediately fail the job.
- Stale terminal writes are ignored.
- SQLite write failures during claim preserve the current safe store-failure behavior where possible.
- Running jobs remain non-cancellable by API in this scope.

## Testing Requirements

SQLite backend tests:

- Claim changes a queued job to running and sets lease metadata.
- Claim returns no job for active lease held by another worker.
- Claim requeues expired running jobs before claiming.
- Heartbeat extends an owned running lease.
- Heartbeat does not update a job owned by another worker.
- Terminal update succeeds only for the owning worker.
- Stale worker terminal update does not overwrite the current attempt.
- Existing SQLite files without lease columns migrate on initialize.
- Active cap still counts queued and running jobs correctly after reclaim.

API/service tests:

- SQLite-backed execution still schedules and completes jobs through the existing endpoint flow.
- Public list/detail responses do not expose lease metadata.
- In-memory backend tests remain unchanged and green.

Use deterministic timestamps and direct helper inputs. Do not use real sleeps.

## Risks

- A local workflow may continue after losing its lease. Ownership-aware terminal writes prevent stale results from overwriting newer attempts.
- Very long blocking workflow phases could miss heartbeat intervals if heartbeat is not independent. The implementation should use a small heartbeat loop while the workflow runs.
- Requeued jobs preserve original `started_at`, so `started_at` means first execution start, not current attempt start. This is acceptable for this scope because no public attempt history is exposed.
