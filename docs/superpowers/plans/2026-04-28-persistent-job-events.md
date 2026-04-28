# Persistent Job Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist safe job execution events so traces and stage progress survive empty in-memory caches.

**Architecture:** Store bounded event history directly on `ResearchJob`. JSON serialization writes the new field, SQLite stores it in `events_json`, and API event reads fall back from memory cache to persisted job events.

**Tech Stack:** Python dataclasses, JSON store, SQLite migration, FastAPI WebSocket, pytest.

---

## File Structure

- Modify `src/insight_graph/research_jobs.py`: add `events` to `ResearchJob`, job detail, and append helper.
- Modify `src/insight_graph/research_jobs_store.py`: serialize/load `events` with backward compatibility.
- Modify `src/insight_graph/research_jobs_sqlite_backend.py`: add `events_json` migration and row mapping.
- Modify `src/insight_graph/api.py`: persist published events and use persisted fallback for replay/progress.
- Modify `tests/test_research_jobs_store.py`: JSON persistence and old-schema compatibility tests.
- Modify `tests/test_research_jobs_sqlite_backend.py`: SQLite column and persistence tests.
- Modify `tests/test_api.py`: WebSocket replay/progress fallback tests.
- Modify `docs/research-jobs-api.md` and `CHANGELOG.md`: document persisted event behavior.

## Task 1: Store Tests

- [ ] Add failing JSON store tests for saving/loading events and old job payloads without events.
- [ ] Add failing SQLite tests for `events_json` schema and persisted event rows.
- [ ] Run store tests and confirm failures are due to missing event support.

## Task 2: Store Implementation

- [ ] Add `events` default field to `ResearchJob`.
- [ ] Update JSON store serialization/loading and validation.
- [ ] Update SQLite schema, migration, `job_to_row()`, and `job_from_row()`.
- [ ] Run store tests and confirm they pass.

## Task 3: API Persistent Replay Tests

- [ ] Add failing API tests for persisted event detail, WebSocket replay after memory clear, and progress from persisted events.
- [ ] Run new API tests and confirm failures are due to memory-only events.

## Task 4: API Implementation

- [ ] Add `append_research_job_event()` in `research_jobs.py` using existing backend update semantics.
- [ ] Import and call it from `_publish_research_job_event()`.
- [ ] Add persisted-event read fallback for replay/progress.
- [ ] Include `events` in job detail responses only.
- [ ] Run new API tests and confirm they pass.

## Task 5: Docs

- [ ] Update `docs/research-jobs-api.md` to describe persisted event replay and detail `events`.
- [ ] Update `CHANGELOG.md` with persistent job events.

## Task 6: Verification

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_research_jobs_store.py tests/test_research_jobs_sqlite_backend.py tests/test_api.py -v`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: JSON, SQLite, API replay, progress fallback, docs, and verification are covered.
- Placeholder scan: no placeholders.
- Type consistency: `events`, `events_json`, and helper names are consistent.
