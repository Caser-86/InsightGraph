# Research Job Repository Spec (2026-04-27)

Overview
- Move internal state management for research jobs into a dedicated module and expose a minimal public maintenance API, to support testability and future extension.

Public API (new)
- reset_research_jobs_state
- seed_research_job / seed_research_jobs
- set_research_jobs_store_path
- set_research_job_limits
- get_research_job_record
- get_next_research_job_sequence
- update_research_job_record

Data model
- ResearchJob: id, query, preset, created_order, created_at, status, started_at, finished_at, result, error

Semantics
- Read operations return copies; mutating copies should not affect internal state.
- For updates, use update_research_job_record.

Thread-safety
- All state mutations are guarded by _JOBS_LOCK.

Backward compatibility
- External API endpoints remain unchanged; internal moves are transparent to API layer.

Migration notes
- Tests updated to use public API; private-state manipulation tests removed.

Testing plan
- Run pytest; run lint; ensure complete test coverage.

Future work
- Consider pluggable storage backends (e.g., database) and corresponding API surface.

References
- File: src/insight_graph/research_jobs.py
- File: tests/test_api.py
- File: tests/test_research_jobs.py
