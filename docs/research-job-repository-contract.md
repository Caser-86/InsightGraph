# Research Job Repository Contract

`src/insight_graph/research_jobs.py` owns the in-process research job repository for the current MVP. This document defines which behaviors are stable contract and which are implementation details.

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
- `get_research_job_record()` returns a copy; mutating the copy must not change repository state.
- State mutation through maintenance helpers must use explicit update APIs such as `update_research_job_record()`.
- Unknown fields in `update_research_job_record()` are rejected.

## In-memory implementation details

- Jobs are stored in a module-level dictionary guarded by `_JOBS_LOCK`.
- Job IDs are generated with `uuid4()`.
- `created_order` is backed by a module-level sequence counter.
- Retention currently prunes oldest terminal jobs only.
- `queued` and `running` jobs are not pruned by terminal-job retention.
- The current implementation is single-process. Multi-process coordination is not part of the MVP contract.

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

Out of scope until storage abstraction exists:
- Job retry/resume.
- Multi-process worker coordination.
- Distributed locks.
- Per-user quotas or auth-aware rate limits.
