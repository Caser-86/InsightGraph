# Changelog

## Unreleased

- Added Dashboard Eval artifact guidance tab.

## v0.1.22 - 2026-04-29

- Added file-based Eval Bench trend history artifacts.

## v0.1.21 - 2026-04-29

- Added Eval Bench trend history design.

## v0.1.20 - 2026-04-29

- Added CI Eval Bench summary artifacts.

## v0.1.19 - 2026-04-29

- Added Eval Bench report summary script.

## v0.1.18 - 2026-04-29

- Added Dashboard Eval Gate visibility.

## v0.1.17 - 2026-04-29

- Added CI Eval Bench report artifacts.

## v0.1.16 - 2026-04-28

- Added Eval Bench case-file loading, a checked-in default case set, CI gate exit codes, and a default CI Eval Gate.

## v0.1.15 - 2026-04-28

- Added `insight-graph-eval` for deterministic offline quality scoring.

## v0.1.14 - 2026-04-28

- Added safe node-level execution events for Planner, Collector, Analyst, Critic, and Reporter.
- Extended WebSocket streams with stage, tool call, LLM call, and report-ready events.
- Added a dashboard Live Events view for real-time agent execution traces.
- Derived running job progress from cached stage events so snapshots show the active graph stage.
- Persisted bounded safe job events in retained job records for replay and progress fallback.

## v0.1.13 - 2026-04-28

- Added a WebSocket research job snapshot stream at `/research/jobs/{job_id}/stream`.
- Updated the dashboard to use WebSocket streaming for selected jobs with polling fallback.
- Documented the FastAPI REST + WebSocket dashboard flow.

## v0.1.12 - 2026-04-28

- Added derived research job progress metadata for dashboard timelines.
- Added protected Markdown and HTML report export endpoints for completed jobs.
- Added dashboard timeline and authenticated report download controls.

## v0.1.11 - 2026-04-28

- Added a static dark-mode dashboard at `GET /dashboard` for creating and polling research jobs.
- Added dashboard views for job metrics, report output, findings, tool calls, LLM metadata, and raw job JSON.
- Documented dashboard usage for local demos and API-key-protected servers.

## v0.1.10 - 2026-04-28

- Added opt-in shared API key authentication with `INSIGHT_GRAPH_API_KEY`.
- Protected `/research` and research job endpoints while keeping `/health` public.
- Documented API key deployment usage, headers, and reverse proxy safety guidance.

## v0.1.9 - 2026-04-28

- Added safe LLM router decision metadata to routed Analyst and Reporter LLM call logs.
- Added Router, Tier, and Reason columns to `--show-llm-log` while keeping prompt and completion content out of logs.
- Included router metadata fields in JSON output for observability automation.

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
