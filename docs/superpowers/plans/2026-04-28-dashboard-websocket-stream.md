# Dashboard WebSocket Stream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight WebSocket job snapshot stream and make the static dashboard use it with polling fallback.

**Architecture:** Keep REST job APIs as source of truth. The WebSocket endpoint accepts a client, authenticates via query parameter when API-key auth is enabled, sends safe job detail snapshots with progress metadata, and closes after terminal jobs. The static dashboard opens one WebSocket for the selected job and falls back to existing polling on stream failure.

**Tech Stack:** FastAPI WebSocket, vanilla dashboard JavaScript, pytest `TestClient.websocket_connect`, ruff.

---

## File Structure

- Modify `src/insight_graph/api.py`: add WebSocket imports, auth helper, snapshot stream helper, and `websocket` route.
- Modify `src/insight_graph/dashboard.py`: add WebSocket state, URL builder, connect/close handlers, and fallback behavior.
- Modify `tests/test_api.py`: add WebSocket stream tests and dashboard marker assertions.
- Modify `README.md`, `docs/demo.md`, `docs/research-jobs-api.md`, `CHANGELOG.md`: document stream endpoint and dashboard behavior.

## Task 1: API WebSocket Stream

- [ ] Add failing tests for successful snapshot, missing job error event, missing API key rejection, and query-param API key success.
- [ ] Run targeted WebSocket tests and confirm they fail because the route is absent.
- [ ] Refactor API-key validation into a reusable helper that supports bearer, `X-API-Key`, and WebSocket query `api_key` candidates.
- [ ] Add `@router.websocket('/research/jobs/{job_id}/stream')` that sends JSON events.
- [ ] Run targeted WebSocket tests and confirm they pass.

## Task 2: Dashboard WebSocket Client

- [ ] Extend dashboard smoke test to assert `connectJobStream`, `closeJobStream`, `WebSocket`, and `/stream` markers.
- [ ] Run dashboard smoke test and confirm it fails.
- [ ] Add dashboard stream state and connection helpers.
- [ ] Open stream after selected job refresh or selected job click.
- [ ] Use stream `job_snapshot` events to update `state.detail` and render the selected job.
- [ ] Fall back to existing polling when the socket errors or closes before terminal status.
- [ ] Run dashboard smoke test and confirm it passes.

## Task 3: Documentation

- [ ] Update README with the WebSocket stream endpoint.
- [ ] Update `docs/demo.md` with dashboard real-time stream behavior.
- [ ] Update `docs/research-jobs-api.md` with stream auth and event shape.
- [ ] Add `v0.1.13` changelog entry.

## Task 4: Verification

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py -v`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: WebSocket endpoint, auth, dashboard connection/fallback, docs, and tests are covered.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: endpoint path and event names match spec and tests.
