# Dashboard v2 Progress Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add derived workflow progress metadata and downloadable Markdown/HTML reports to the existing static dashboard and API.

**Architecture:** Keep research job storage unchanged and derive progress/export data from public job fields and completed job results. The API owns response shaping and protected report endpoints; the static dashboard consumes the same JSON fields and downloads reports through authenticated `fetch`.

**Tech Stack:** FastAPI, Pydantic, vanilla HTML/CSS/JavaScript, pytest `TestClient`, ruff.

---

## File Structure

- Modify `src/insight_graph/api.py`: add response models, progress derivation helpers, report export routes, and HTML escaping.
- Modify `src/insight_graph/dashboard.py`: add timeline CSS/HTML rendering, selected-job metrics, and authenticated report download buttons.
- Modify `tests/test_api.py`: add progress/export/dashboard smoke tests and update route/openapi expectations.
- Modify `README.md`, `docs/demo.md`, `docs/research-jobs-api.md`, `CHANGELOG.md`: document dashboard v2 and report export.

## Task 1: Progress Metadata

- [ ] Write failing tests for queued, running, succeeded, failed, and cancelled job detail progress fields in `tests/test_api.py`.
- [ ] Run targeted tests and confirm they fail because fields are absent.
- [ ] Add progress response models and helper functions in `src/insight_graph/api.py`.
- [ ] Wrap `get_research_job()` and cancel responses with derived progress metadata.
- [ ] Run targeted tests and confirm they pass.

## Task 2: Report Export Endpoints

- [ ] Write failing tests for `/research/jobs/{job_id}/report.md`, `/research/jobs/{job_id}/report.html`, unavailable report `409`, unknown job `404`, and auth protection.
- [ ] Run targeted tests and confirm they fail because routes are absent.
- [ ] Add report lookup helper, Markdown response route, and escaped HTML response route in `src/insight_graph/api.py`.
- [ ] Add route paths to route inventory and OpenAPI assertions where applicable.
- [ ] Run targeted tests and confirm they pass.

## Task 3: Dashboard UI

- [ ] Extend dashboard smoke test to assert `progress-timeline`, `download-md`, `download-html`, `renderProgressTimeline`, and `downloadReport` markers.
- [ ] Run dashboard smoke test and confirm it fails because markers are absent.
- [ ] Add timeline CSS and selected-job progress rendering in `src/insight_graph/dashboard.py`.
- [ ] Add report download buttons that call authenticated `fetch` and create a temporary object URL.
- [ ] Run dashboard smoke test and confirm it passes.

## Task 4: Documentation

- [ ] Update README API section with report export endpoints.
- [ ] Update `docs/demo.md` dashboard section with progress and export behavior.
- [ ] Update `docs/research-jobs-api.md` with derived progress fields and report export status codes.
- [ ] Update `CHANGELOG.md` with the next unreleased entry.

## Task 5: Verification

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py -v`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: progress metadata, dashboard timeline, report export, auth, unavailable reports, docs, and verification are covered.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: route names, response field names, and dashboard marker names match the design.
