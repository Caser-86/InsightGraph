# Demo Dashboard UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a polished, screenshot-inspired static dashboard at `/dashboard` for creating, polling, and inspecting InsightGraph research jobs.

**Architecture:** The FastAPI app serves one public HTML page from a focused `dashboard.py` module. The browser page uses dependency-free inline CSS/JavaScript and calls the existing research job API with optional bearer auth from a local API key input.

**Tech Stack:** FastAPI `HTMLResponse`, vanilla HTML/CSS/JavaScript, existing `/research/jobs*` endpoints, pytest `TestClient`, ruff.

---

## File Structure

- Create `src/insight_graph/dashboard.py`: owns the self-contained dashboard HTML string and a `dashboard_html()` accessor.
- Modify `src/insight_graph/api.py`: imports the dashboard helper, adds public `GET /dashboard` returning `HTMLResponse`.
- Modify `tests/test_api.py`: adds route/public tests and updates route inventory expectations.
- Modify `README.md`: documents the dashboard entrypoint.
- Modify `docs/demo.md`: adds dashboard demo instructions.

## Task 1: Public Dashboard Route

**Files:**

- Create: `src/insight_graph/dashboard.py`
- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing route tests**

Add these tests near existing health/auth route tests in `tests/test_api.py`:

```python
def test_dashboard_returns_html() -> None:
    client = TestClient(api_module.app)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "InsightGraph Dashboard" in response.text
    assert "data-insightgraph-dashboard" in response.text


def test_dashboard_remains_public_when_api_key_is_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "InsightGraph Dashboard" in response.text
```

Update `test_module_level_app_remains_configured`:

```python
def test_module_level_app_remains_configured() -> None:
    route_paths = {route.path for route in api_module.app.routes}

    assert "/dashboard" in route_paths
    assert "/health" in route_paths
    assert "/research/jobs" in route_paths
    assert "/research/jobs/{job_id}" in route_paths
```

- [ ] **Step 2: Run route tests and verify failure**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py::test_dashboard_returns_html tests/test_api.py::test_dashboard_remains_public_when_api_key_is_configured tests/test_api.py::test_module_level_app_remains_configured -v
```

Expected: at least `test_dashboard_returns_html` fails with `404` before implementation.

- [ ] **Step 3: Add minimal dashboard module**

Create `src/insight_graph/dashboard.py`:

```python
_DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>InsightGraph Dashboard</title>
</head>
<body data-insightgraph-dashboard>
  <main>
    <h1>InsightGraph Dashboard</h1>
  </main>
</body>
</html>
"""


def dashboard_html() -> str:
    return _DASHBOARD_HTML
```

- [ ] **Step 4: Add public FastAPI route**

Modify imports in `src/insight_graph/api.py`:

```python
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
```

Add import:

```python
from insight_graph.dashboard import dashboard_html
```

Add route after `health()`:

```python
@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    return HTMLResponse(dashboard_html())
```

- [ ] **Step 5: Run route tests and verify pass**

Run the same command from Step 2.

Expected: all three tests pass.

## Task 2: Screenshot-Inspired Static UI

**Files:**

- Modify: `src/insight_graph/dashboard.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Extend HTML smoke test**

Add assertions to `test_dashboard_returns_html`:

```python
    assert "id=\"dashboard-root\"" in response.text
    assert "id=\"query-input\"" in response.text
    assert "id=\"job-list\"" in response.text
    assert "id=\"report-panel\"" in response.text
    assert "fetch('/research/jobs" in response.text
```

- [ ] **Step 2: Run dashboard test and verify failure**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py::test_dashboard_returns_html -v
```

Expected: fails because the detailed dashboard markup is not present.

- [ ] **Step 3: Replace minimal HTML with full static dashboard**

Update `src/insight_graph/dashboard.py` so `_DASHBOARD_HTML` contains:

- Dark navy gradient page background.
- Header with `IG InsightGraph`, `Research Command Center`, status pill, and auto refresh toggle.
- Launch console with API key, preset, query, submit, refresh.
- Metric strip with total/queued/running/succeeded/failed/active load.
- Job cards list.
- Detail tabs: Overview, Report, Findings, Tool Calls, LLM Log, Raw JSON.
- Dependency-free JavaScript functions for auth headers, API calls, polling, job selection, safe HTML escaping, minimal markdown rendering, cancel, and retry.

The page must include these stable markers used by tests:

```html
<body data-insightgraph-dashboard>
<div id="dashboard-root" class="shell">
<textarea id="query-input"></textarea>
<div id="job-list" class="job-list"></div>
<section id="report-panel" class="panel tab-panel"></section>
```

The JavaScript must call existing relative endpoints:

```javascript
fetch('/research/jobs', {
fetch('/research/jobs/summary', {
fetch(`/research/jobs/${encodeURIComponent(jobId)}`, {
```

- [ ] **Step 4: Run dashboard HTML smoke test**

Run the command from Step 2.

Expected: pass.

## Task 3: Dashboard Docs

**Files:**

- Modify: `README.md`
- Modify: `docs/demo.md`

- [ ] **Step 1: Update README API/Demo sections**

In `README.md`, add `/dashboard` to the API capability row and add a short dashboard usage block under API MVP:

```markdown
Dashboard:

```text
http://127.0.0.1:8000/dashboard
```

The dashboard is a static local UI for creating and polling research jobs. If `INSIGHT_GRAPH_API_KEY` is configured, enter the same key in the dashboard API key field before submitting or refreshing jobs.
```

- [ ] **Step 2: Update demo guide**

In `docs/demo.md`, add a Dashboard Demo section after Offline Smoke Demo:

```markdown
## Dashboard Demo

Start the API server:

```bash
python -m pip install "uvicorn[standard]"
uvicorn insight_graph.api:app --reload
```

Open:

```text
http://127.0.0.1:8000/dashboard
```

Submit an offline query from the dashboard, then watch the job list, status cards, report, tool calls, and LLM metadata tabs update as the job completes. If `INSIGHT_GRAPH_API_KEY` is set, enter that key in the dashboard before using job actions.
```

## Task 4: Verification

**Files:**

- Verify only; no source edits expected unless a command fails.

- [ ] **Step 1: Run targeted API tests**

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py -v
```

Expected: all API tests pass.

- [ ] **Step 2: Run full test suite**

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
```

Expected: all tests pass with the existing skipped count unchanged.

- [ ] **Step 3: Run ruff**

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 4: Run whitespace check**

```powershell
git diff --check
```

Expected: no output and exit code 0.

## Self-Review

- Spec coverage: route, public dashboard, visual direction, job APIs, auth headers, polling, errors, tests, and docs are covered.
- Placeholder scan: no TODO/TBD placeholders remain.
- Type consistency: route names, test names, endpoints, and file paths match the current FastAPI/test structure.
