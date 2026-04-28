# Research Job Repository Contract

`src/insight_graph/research_jobs.py` owns the service-facing research job repository contract for the current MVP. `src/insight_graph/research_jobs_backend.py` owns the in-memory backend used by that service layer. This document defines which behaviors are stable contract and which are implementation details.

## Stable contract

- Job statuses are `queued`, `running`, `succeeded`, `failed`, and `cancelled`.
- Active jobs are `queued` and `running`.
- Terminal jobs are `succeeded`, `failed`, and `cancelled`.
- `created_at` is set when a job is created.
- `started_at` is set when a job enters `running`.
- `finished_at` is set when a job enters a terminal state.
- Queue position is dynamic and applies only to `queued` jobs.
- Detail responses expose `result` only for `succeeded` jobs.
- Detail responses expose safe `error` only for `failed` jobs.
- List and summary responses do not expose result payloads or provider exception details.
- Manual retry creates a new queued job from a failed or cancelled source job; the source job is not mutated.
- `get_research_job_record()` returns a copy; mutating the copy must not change repository state.
- State mutation through maintenance helpers must use explicit update APIs such as `update_research_job_record()`.
- Unknown fields in `update_research_job_record()` are rejected.

## Service/backend boundary

- `research_jobs.py` remains the API-facing service layer for validation, response shaping, persistence calls, rollback decisions, and worker scheduling.
- `research_jobs_backend.py` owns low-level in-memory state access through `InMemoryResearchJobsBackend`.
- Backend-owned helpers include active-job counting, terminal-job pruning, snapshot/restore, job copy reads, explicit updates, seeding, clearing, and sequence tracking.
- The backend boundary is an internal seam, not a public storage plugin API.
- SQLite storage is optional and must preserve the same public repository contract as the in-memory backend.
- SQLite adds internal worker leasing without public API response changes.
- Runtime backend selection is explicit via `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND`; SQLite also requires `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH`.
- API handlers and tests should prefer the public service helpers instead of mutating module globals directly.
- Implementation links: [#2](https://github.com/Caser-86/InsightGraph/issues/2), [#3](https://github.com/Caser-86/InsightGraph/issues/3), [`c8d3853`](https://github.com/Caser-86/InsightGraph/commit/c8d385386b6b9f5ca0d7a8cf65d52d7a11a76f08), [`9985245`](https://github.com/Caser-86/InsightGraph/commit/99852450a22c65aa8dee7f419a61a3b1f0275866).

## In-memory backend details

- Jobs are stored in a dictionary owned by `InMemoryResearchJobsBackend` and guarded by a re-entrant lock.
- Job IDs are generated with `uuid4()`.
- `created_order` is backed by an in-memory sequence counter.
- Retention currently prunes oldest terminal jobs only through backend pruning helpers.
- `queued` and `running` jobs are not pruned by terminal-job retention.
- The current implementation is single-process. Multi-process coordination is not part of the MVP contract.

## SQLite worker leasing

When the SQLite backend is selected, background execution uses internal worker leases.

- Workers claim queued jobs before running workflows.
- Claiming sets internal lease metadata and moves the job to `running`.
- Expired `running` jobs are requeued on later claim attempts.
- Heartbeats extend leases while workflows run.
- Terminal writes are accepted only from the worker that owns the lease.
- Lease metadata is internal and is not exposed by API responses.

The in-memory backend keeps its existing single-process behavior and does not simulate leases.

## Persistence and rollback contract

- If configured persistence is unavailable during job creation, the new job is not committed and no worker is scheduled.
- If persistence fails during job creation after pruning, the previous job set and sequence are restored.
- If persistence fails while cancelling a job, the job status and `finished_at` are restored.
- If persistence fails while marking a job `running`, the job is marked `failed` with safe error `Research job store failed.`.
- Terminal-state persistence is best-effort after workflow completion; store failures do not expose provider details to API clients.

## Future storage backend requirements

Any SQLite/Postgres or external storage backend must preserve the stable contract above before replacing the in-memory implementation.

Required backend capabilities:
- Atomic create with active-cap check.
- Atomic cancel with queued-only precondition.
- Atomic transition from queued to running unless already cancelled.
- Stable ordering by `created_order`.
- Dynamic queue position calculation for queued jobs.
- Rollback or equivalent transactional behavior for create/cancel failures.
- Safe error shaping at API boundaries.

Out of scope:
- Automatic job resume beyond SQLite expired-lease requeue.
- Distributed locks outside SQLite row updates.
- Per-user quotas or auth-aware rate limits.
- Postgres-backed storage.
