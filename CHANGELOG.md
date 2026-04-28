# Changelog

## v0.1.8 - 2026-04-28

- Added opt-in internal LLM rules router with user-defined fast/default/strong model tiers.
- Routed analyst and reporter LLM client creation with purpose and prompt-size context.
- Documented LiteLLM Proxy usage through the existing OpenAI-compatible base URL path.

## v0.1.7 - 2026-04-28

- Added SQLite worker leasing for research jobs to coordinate multi-process execution.
- Requeued expired running SQLite jobs for later workers to claim.
- Added lease heartbeat and ownership-aware terminal writes so stale workers cannot overwrite newer attempts.
- Documented internal SQLite leasing semantics and updated roadmap status.

## v0.1.6 - 2026-04-28

- Added manual retry for failed or cancelled research jobs.
- Added `POST /research/jobs/{job_id}/retry` to create a new queued retry job without mutating the source job.
- Documented retry status codes and added memory/SQLite retry contract coverage.

## v0.1.5 - 2026-04-28

- Added explicit runtime env selection for research job storage.
- Added `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND` and `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH`.
- Documented SQLite runtime storage configuration and guarded JSON-to-SQLite startup import.

## v0.1.4 - 2026-04-28

- Added optional `SQLiteResearchJobsBackend` for research job storage.
- Added SQLite schema, sequence metadata, state helpers, JSON store import, and transactional job lifecycle updates.
- Added memory/SQLite backend contract tests while keeping public API behavior unchanged.

## v0.1.3 - 2026-04-28

- Added research job backend boundary documentation.
- Added SQLite-first database storage design and implementation plan.
- Closed backend boundary planning issues #4 and #5.

## v0.1.2 - 2026-04-28

- Added in-memory research job backend boundary.
- Moved active count, terminal pruning, snapshot/restore, and sequence helpers into the backend.
- Fixed backend annotation compatibility for Python 3.11 CI.

## v0.1.1 - 2026-04-27

- Split research job state management into `src/insight_graph/research_jobs.py`.
- Added public maintenance helpers for resetting state, seeding jobs, setting limits/store path, copy-on-read inspection, and explicit job updates.
- Migrated research job/API tests away from direct private state access.
- Added repository helper spec: `docs/superpowers/specs/2026-04-27-research-job-repo-spec.md`.
