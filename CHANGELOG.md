# Changelog

## v0.1.1 - 2026-04-27

- Split research job state management into `src/insight_graph/research_jobs.py`.
- Added public maintenance helpers for resetting state, seeding jobs, setting limits/store path, copy-on-read inspection, and explicit job updates.
- Migrated research job/API tests away from direct private state access.
- Added repository helper spec: `docs/superpowers/specs/2026-04-27-research-job-repo-spec.md`.
