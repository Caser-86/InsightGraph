# Research Job Storage Abstraction Design

## Goal

Define a future storage abstraction for research jobs before adding SQLite/Postgres or multi-process worker coordination.

## Current state

- `src/insight_graph/research_jobs.py` owns job lifecycle, response shaping, in-memory state, lock usage, pruning, rollback snapshots, and JSON persistence orchestration.
- `src/insight_graph/research_jobs_store.py` serializes/deserializes JSON metadata for opt-in persistence.
- API endpoint behavior is already documented in `docs/research-jobs-api.md`.
- Repository behavior is already documented in `docs/research-job-repository-contract.md`.

## Stable contract to preserve

- Endpoint paths, status codes, and response shapes stay unchanged.
- `queued + running` active cap stays enforced before job creation commits.
- Terminal retention prunes only `succeeded`, `failed`, and `cancelled` jobs.
- Queue positions remain dynamic and 1-based for queued jobs only.
- Create/cancel persistence failures preserve current rollback semantics.
- Running transition persistence failure marks job `failed` with safe error `Research job store failed.`.
- Terminal persistence remains best-effort unless a later spec explicitly changes it.

## Proposed boundary

Introduce a backend boundary below the existing public repository functions. Keep `research_jobs.py` as the API-facing service layer and move state operations behind an internal backend interface.

Initial backend interface should support:

- reset state for tests/maintenance
- seed jobs for tests/maintenance
- inspect one job by ID with copy-on-read
- update one job with known-field validation
- create job atomically with active-cap check
- list summaries newest first with optional status/limit
- summarize counts, active jobs, and limits
- cancel queued job atomically
- mark queued job running unless cancelled
- mark job failed/succeeded with terminal pruning
- initialize from persisted JSON state
- persist state or no-op when store path is unset

## First implementation shape

- Keep only an in-memory backend at first.
- Do not add SQLite/Postgres in the same change.
- Do not add retry/resume in the same change.
- Do not add distributed locking in the same change.
- Add contract tests that exercise behavior through public repository functions, not private fields.

## Future database backend requirements

SQLite/Postgres backend must provide transaction boundaries for:

- create job + active-cap check + terminal pruning + persist/commit
- cancel queued job + terminal pruning + commit/rollback
- mark running unless cancelled
- terminal status update + best-effort or transactional policy chosen by a later spec

The database backend must also preserve sorting by `created_order` and dynamic queue-position calculation.

## Non-goals

- No external API behavior change.
- No JSON store schema change unless separately specified.
- No automatic job resume after restart.
- No multi-process worker leasing.
- No auth, quotas, or per-user job limits.
