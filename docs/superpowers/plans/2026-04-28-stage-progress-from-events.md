# Stage Progress From Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make running job progress reflect cached execution stage events instead of always showing planner.

**Architecture:** Reuse the in-memory job event broker as a read model for running job progress. `_research_job_progress()` derives stage status from cached `stage_started` and `stage_finished` events for the job id, while terminal job statuses keep their existing deterministic behavior.

**Tech Stack:** Python helper functions in FastAPI module, pytest, existing static dashboard timeline.

---

## File Structure

- Modify `src/insight_graph/api.py`: add event-derived progress helper functions and wire them into `_research_job_progress()`.
- Modify `tests/test_api.py`: add tests for REST and WebSocket snapshots with cached stage events.
- Modify `docs/research-jobs-api.md`: document that snapshot progress can derive from cached stage events.
- Modify `CHANGELOG.md`: add bullet for event-derived stage progress.

## Task 1: Failing Progress Tests

- [ ] Add `test_get_research_job_derives_running_progress_from_stage_events` to `tests/test_api.py`.
- [ ] Add `test_research_job_stream_snapshot_uses_stage_event_progress` to `tests/test_api.py`.
- [ ] Add `test_get_research_job_derives_failed_stage_from_stage_events` to `tests/test_api.py`.
- [ ] Run the three tests and verify they fail because running progress still falls back to planner and failed progress marks planner failed.

## Task 2: Event-Derived Progress Implementation

- [ ] Add a `_stage_progress_from_events(job_id, status)` helper in `src/insight_graph/api.py`.
- [ ] Add stage percent mapping: planner 20, collector 40, analyst 60, critic 80, reporter 95.
- [ ] Update `_research_job_progress(job)` to use cached events for running and failed jobs when `job_id` exists.
- [ ] Run the three new tests and verify they pass.

## Task 3: Docs

- [ ] Update `docs/research-jobs-api.md` to describe event-derived progress in snapshots.
- [ ] Update `CHANGELOG.md` with a stage progress bullet.

## Task 4: Verification

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py::test_get_research_job_derives_running_progress_from_stage_events tests/test_api.py::test_research_job_stream_snapshot_uses_stage_event_progress tests/test_api.py::test_get_research_job_derives_failed_stage_from_stage_events -v`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py tests/test_graph.py -v`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: running REST progress, WebSocket snapshots, failed-stage fallback, docs, and verification are covered.
- Placeholder scan: no placeholders.
- Type consistency: helper names, event types, and progress fields match existing code.
