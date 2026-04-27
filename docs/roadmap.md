# Roadmap

## Near-term priorities

1. Strengthen research job repository tests
- Add boundary tests for `update_research_job_record()` when job IDs are missing.
- Add tests for invalid update fields or decide whether updates remain trusted maintenance-only calls.
- Add lightweight lock/concurrency tests around state reset, seed, inspect, and update helpers.

2. Clarify repository/storage contract
- Define which `research_jobs.py` behaviors are stable repository contract versus in-memory implementation detail.
- Document rollback behavior for create/cancel/persist failures.
- Prepare a storage interface plan before any SQLite/Postgres migration.

3. Keep API docs aligned with runtime behavior
- Keep OpenAPI examples aligned with queued/running/terminal job states.
- Document active cap and retained terminal job cap where clients can find it.
- Add examples for list filtering, limit handling, summary, and cancel conflict responses.

4. Improve release workflow
- Ensure CI runs `python -m pytest` and `python -m ruff check .`.
- Decide whether tags/releases are manual or automated after `master` merges.
- Keep `CHANGELOG.md` updated for each released tag.

## Deferred work

- Add job retry/resume semantics only after persistence contract is stable.
- Add multi-process job coordination only after storage abstraction exists.
- Add auth/rate limits only when API moves beyond local MVP usage.
