# Node Event Stream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit safe node-level execution events from research jobs and show them live in the dashboard WebSocket stream.

**Architecture:** Add an event-emitting graph runner that mirrors the existing graph topology with direct node calls. The API job worker publishes events into a bounded in-memory broker, and the WebSocket endpoint sends the initial job snapshot, cached events, then live broker events.

**Tech Stack:** Python callbacks, FastAPI WebSocket, queue-based in-memory pub/sub, vanilla dashboard JavaScript, pytest.

---

## File Structure

- Modify `src/insight_graph/graph.py`: add `run_research_with_events()` and safe stage/delta event emission.
- Modify `src/insight_graph/api.py`: add broker state/helpers, publish worker events, extend WebSocket stream.
- Modify `src/insight_graph/dashboard.py`: add Live Events UI and handle non-snapshot stream events.
- Modify `tests/test_graph.py`: add graph runner event tests.
- Modify `tests/test_api.py`: add stream replay and dashboard marker tests.
- Modify docs/changelog files: document live execution events.

## Task 1: Event-Emitting Graph Runner

- [ ] Add failing graph tests for stage event order and tool/LLM event emission.
- [ ] Run targeted graph tests and confirm they fail because `run_research_with_events` is absent.
- [ ] Implement `run_research_with_events()` in `src/insight_graph/graph.py`.
- [ ] Run targeted graph tests and confirm they pass.

## Task 2: API Event Broker and Worker Publishing

- [ ] Add failing API tests for cached event replay and worker-published events.
- [ ] Run targeted API tests and confirm they fail.
- [ ] Add bounded event broker helpers in `src/insight_graph/api.py`.
- [ ] Change `_run_research_job()` to call `run_research_with_events()` and publish job-scoped events.
- [ ] Extend WebSocket stream to send cached events after the initial snapshot and live events while waiting.
- [ ] Run targeted API tests and confirm they pass.

## Task 3: Dashboard Live Events

- [ ] Extend dashboard smoke test with `live-events`, `renderLiveEvent`, and event handler markers.
- [ ] Run dashboard smoke test and confirm it fails.
- [ ] Add Live Events tab and state storage.
- [ ] Render stage/tool/LLM/report events safely.
- [ ] Handle stream events in WebSocket `onmessage`.
- [ ] Run dashboard smoke test and confirm it passes.

## Task 4: Documentation

- [ ] Update README dashboard description.
- [ ] Update `docs/demo.md` with live execution event behavior.
- [ ] Update `docs/research-jobs-api.md` with stream event types.
- [ ] Add changelog entry for the next release.

## Task 5: Verification

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_graph.py tests/test_api.py -v`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: graph events, broker, WebSocket replay/live events, dashboard UI, docs, and verification are covered.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: event types and function names match the design.
