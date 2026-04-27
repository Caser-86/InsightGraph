# Research Job SQLite Environment Enablement Design

## Goal

Let operators enable the SQLite research job backend at runtime with explicit environment variables while preserving the current in-memory default and JSON metadata behavior.

## Scope

- Add explicit backend selection for research jobs.
- Keep in-memory backend as default when no backend env is set.
- Keep existing JSON metadata store behavior unchanged for the in-memory backend.
- Allow optional one-time JSON import when SQLite is selected and `INSIGHT_GRAPH_RESEARCH_JOBS_PATH` points at an existing JSON store.

## Environment Variables

- `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND`
  - unset or `memory`: use current in-memory backend.
  - `sqlite`: use `SQLiteResearchJobsBackend`.
- `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH`
  - required when backend is `sqlite`.
  - points to the SQLite database file.
- `INSIGHT_GRAPH_RESEARCH_JOBS_PATH`
  - unchanged JSON metadata path.
  - when SQLite backend is selected, this path is only an optional JSON import source during `initialize_research_jobs()`.

## Behavior

- Missing SQLite path with `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite` fails closed during backend configuration.
- Unknown backend values fail closed with a clear configuration error.
- API paths, response bodies, statuses, worker behavior, queue positions, active limits, and terminal retention remain unchanged.
- SQLite backend does not add retry/resume, worker leasing, distributed locks, or public API changes.

## Implementation Shape

- Add env parsing helpers near existing research job store env helpers.
- Add service-layer backend configuration from env in `research_jobs.py`.
- Keep test helpers `configure_research_jobs_in_memory_backend()` and `configure_research_jobs_sqlite_backend()`.
- Ensure `initialize_research_jobs()` initializes/imports according to selected backend.
- Add tests for default memory behavior, explicit SQLite selection, missing path failure, unknown backend failure, and optional JSON import.

## Non-goals

- No CLI flags.
- No Postgres backend.
- No automatic migration command.
- No multi-process worker leasing.
- No change to existing JSON store schema.

## Success Criteria

- Existing tests keep passing with no env set.
- New env tests prove SQLite selection works with API/service helpers.
- Misconfiguration fails with deterministic error.
- Docs explain all three env vars and their interaction.
