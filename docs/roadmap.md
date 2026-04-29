# Roadmap

## Canonical Route

The active project route is now `docs/report-quality-roadmap.md`.

Future work must follow that document unless the user explicitly approves a route change. The previous near-term engineering work is considered complete enough for the next phase. Do not continue adding deployment, dashboard, smoke-test, auth, storage, or eval convenience features unless they directly support the report-quality route or fix a bug/security/CI failure.

## Near-term priorities

1. Strengthen research job repository tests
- Done: boundary tests for `update_research_job_record()` when job IDs are missing.
- Done: invalid update field tests for `update_research_job_record()`.
- Done: lightweight lock/concurrency test around explicit job updates.

2. Clarify repository/storage contract
- Done: stable contract documented in `docs/research-job-repository-contract.md`.
- Done: rollback behavior documented for create/cancel/persist failures.
- Done: storage interface design and plan saved under `docs/superpowers/`.
- Done: implemented backend boundary documented with service/backend responsibilities and implementation links.
- Done: SQLite worker leasing coordinates multi-process job execution and requeues expired running jobs.

3. Keep API docs aligned with runtime behavior
- Done: OpenAPI examples aligned with queued/running/terminal job states.
- Done: active cap and retained terminal job cap documented in `docs/research-jobs-api.md`.
- Done: examples for list filtering, limit handling, summary, and cancel conflict responses.

4. Improve release workflow
- Done: CI runs `python -m pytest` and `python -m ruff check .` on pushes to `master` and pull requests.
- Done: CI runs the default Eval Bench gate with `docs/evals/default.json`.
- Done: CI uploads `eval-reports` containing Eval Bench full, summary, and history reports.
- Done: deployment hardening checklist documents public demo boundaries.
- Done: CI validates the deployment smoke test script entry point without network access.
- Manual: tags/releases remain manual after `master` merges.
- Manual: keep `CHANGELOG.md` updated for each released tag.

## Deferred work

- Add automatic job resume semantics only after persistence contract is stable; manual retry is already implemented.
- Add built-in rate limits only when API moves beyond local MVP usage; public demos should use reverse proxy or API gateway limits.
