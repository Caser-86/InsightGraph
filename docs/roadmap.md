# Roadmap

## Near-term priorities

1. Strengthen research job repository tests
- Done: boundary tests for `update_research_job_record()` when job IDs are missing.
- Done: invalid update field tests for `update_research_job_record()`.
- Done: lightweight lock/concurrency test around explicit job updates.

2. Clarify repository/storage contract
- Done: stable contract documented in `docs/research-job-repository-contract.md`.
- Done: rollback behavior documented for create/cancel/persist failures.
- Done: storage interface design and plan saved under `docs/superpowers/`.

3. Keep API docs aligned with runtime behavior
- Done: OpenAPI examples aligned with queued/running/terminal job states.
- Done: active cap and retained terminal job cap documented in `docs/research-jobs-api.md`.
- Done: examples for list filtering, limit handling, summary, and cancel conflict responses.

4. Improve release workflow
- Done: CI runs `python -m pytest` and `python -m ruff check .` on pushes to `master` and pull requests.
- Manual: tags/releases remain manual after `master` merges.
- Manual: keep `CHANGELOG.md` updated for each released tag.

## Deferred work

- Add job retry/resume semantics only after persistence contract is stable.
- Add multi-process job coordination only after storage abstraction exists.
- Add auth/rate limits only when API moves beyond local MVP usage.
