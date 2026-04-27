# API Jobs List Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `status` and `limit` query controls to `GET /research/jobs` while preserving the existing response shape.

**Architecture:** Keep the filtering logic inside the existing FastAPI module and response builder. FastAPI query validation constrains incoming parameters, `_jobs_list_response_locked()` filters and slices the in-memory jobs, and the existing `ResearchJobsListResponse` response model remains unchanged.

**Tech Stack:** Python 3.11+, FastAPI query parameters, Pydantic response models, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/api.py`: import FastAPI query helpers, define a reusable job status query type, add `status` and `limit` query parameters to `list_research_jobs()`, and update `_jobs_list_response_locked()` to filter and limit summaries.
- Modify `tests/test_api.py`: add API tests for status filtering, limiting, validation failures, global queue positions, and OpenAPI query parameter documentation.
- Modify `docs/architecture.md`: update the current API jobs description to mention `status` and `limit` list controls.

## Task 1: Add Failing API Tests For Filtering And Limits

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add tests after `test_list_research_jobs_returns_summaries_newest_first`**

Insert this code immediately after the existing list test in `tests/test_api.py`:

```python
def test_list_research_jobs_filters_by_status(monkeypatch) -> None:
    fake_executor = FakeExecutor()

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence(
            "2026-04-27T18:00:00Z",
            "2026-04-27T18:00:01Z",
            "2026-04-27T18:00:02Z",
            "2026-04-27T18:00:03Z",
            "2026-04-27T18:00:04Z",
            "2026-04-27T18:00:05Z",
        ),
    )
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    queued = client.post("/research/jobs", json={"query": "Queued"}).json()["job_id"]
    running = client.post("/research/jobs", json={"query": "Running"}).json()["job_id"]
    with api_module._JOBS_LOCK:
        api_module._JOBS[running].status = "running"
        api_module._JOBS[running].started_at = "2026-04-27T18:00:03Z"

    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", ImmediateExecutor())
    succeeded = client.post("/research/jobs", json={"query": "Succeeded"}).json()[
        "job_id"
    ]

    response = client.get("/research/jobs", params={"status": "queued"})

    assert response.status_code == 200
    assert response.json() == {
        "jobs": [
            {
                "job_id": queued,
                "status": "queued",
                "query": "Queued",
                "preset": "offline",
                "created_at": "2026-04-27T18:00:00Z",
                "queue_position": 1,
            }
        ],
        "count": 1,
    }
    assert running not in response.text
    assert succeeded not in response.text


def test_list_research_jobs_limits_newest_matching_jobs(monkeypatch) -> None:
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    monkeypatch.setattr(
        api_module,
        "_current_utc_timestamp",
        timestamp_sequence(
            "2026-04-27T19:00:00Z",
            "2026-04-27T19:00:01Z",
            "2026-04-27T19:00:02Z",
        ),
    )
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    oldest = client.post("/research/jobs", json={"query": "Oldest"}).json()["job_id"]
    middle = client.post("/research/jobs", json={"query": "Middle"}).json()["job_id"]
    newest = client.post("/research/jobs", json={"query": "Newest"}).json()["job_id"]

    response = client.get("/research/jobs", params={"status": "queued", "limit": 2})

    assert response.status_code == 200
    assert response.json() == {
        "jobs": [
            {
                "job_id": newest,
                "status": "queued",
                "query": "Newest",
                "preset": "offline",
                "created_at": "2026-04-27T19:00:02Z",
                "queue_position": 3,
            },
            {
                "job_id": middle,
                "status": "queued",
                "query": "Middle",
                "preset": "offline",
                "created_at": "2026-04-27T19:00:01Z",
                "queue_position": 2,
            },
        ],
        "count": 2,
    }
    assert oldest not in response.text
```

- [ ] **Step 2: Run tests and verify they fail for the expected reason**

Run:

```bash
python -m pytest tests/test_api.py::test_list_research_jobs_filters_by_status tests/test_api.py::test_list_research_jobs_limits_newest_matching_jobs -q
```

Expected: both tests fail because `GET /research/jobs` ignores `status` and `limit`, so extra jobs appear in the response.

## Task 2: Implement Status Filtering And Limit Validation

**Files:**
- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Update imports in `src/insight_graph/api.py`**

Change the imports near the top of `src/insight_graph/api.py` from:

```python
from typing import Any

from fastapi import FastAPI, HTTPException
```

to:

```python
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Query
```

- [ ] **Step 2: Add query parameter aliases after `_RESEARCH_JOB_STATUSES`**

Insert this code after the `_RESEARCH_JOB_STATUSES` tuple:

```python
ResearchJobStatusQuery = Literal[
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
]
ResearchJobsLimitQuery = Annotated[int, Query(ge=1, le=100)]
```

- [ ] **Step 3: Update `_jobs_list_response_locked`**

Replace the existing function:

```python
def _jobs_list_response_locked() -> dict[str, Any]:
    jobs = sorted(
        _JOBS.values(),
        key=lambda item: item.created_order,
        reverse=True,
    )
    queued_positions = _queued_job_positions_locked()
    summaries = [_job_summary(job, queued_positions) for job in jobs]
    return {"jobs": summaries, "count": len(summaries)}
```

with:

```python
def _jobs_list_response_locked(
    status: ResearchJobStatusQuery | None,
    limit: int,
) -> dict[str, Any]:
    jobs = sorted(
        _JOBS.values(),
        key=lambda item: item.created_order,
        reverse=True,
    )
    if status is not None:
        jobs = [job for job in jobs if job.status == status]
    jobs = jobs[:limit]

    queued_positions = _queued_job_positions_locked()
    summaries = [_job_summary(job, queued_positions) for job in jobs]
    return {"jobs": summaries, "count": len(summaries)}
```

- [ ] **Step 4: Update `list_research_jobs` endpoint signature**

Replace the existing endpoint function:

```python
def list_research_jobs() -> dict[str, Any]:
    with _JOBS_LOCK:
        return _jobs_list_response_locked()
```

with:

```python
def list_research_jobs(
    status: ResearchJobStatusQuery | None = None,
    limit: ResearchJobsLimitQuery = 100,
) -> dict[str, Any]:
    with _JOBS_LOCK:
        return _jobs_list_response_locked(status=status, limit=limit)
```

- [ ] **Step 5: Run the focused tests and verify they pass**

Run:

```bash
python -m pytest tests/test_api.py::test_list_research_jobs_filters_by_status tests/test_api.py::test_list_research_jobs_limits_newest_matching_jobs -q
```

Expected: `2 passed`.

## Task 3: Add Query Validation And OpenAPI Tests

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add validation tests after the Task 1 tests**

Insert this code after `test_list_research_jobs_limits_newest_matching_jobs`:

```python
def test_list_research_jobs_rejects_invalid_status() -> None:
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    response = client.get("/research/jobs", params={"status": "unknown"})

    assert response.status_code == 422


def test_list_research_jobs_rejects_invalid_limits() -> None:
    api_module._JOBS.clear()
    client = TestClient(api_module.app)

    too_small = client.get("/research/jobs", params={"limit": 0})
    too_large = client.get("/research/jobs", params={"limit": 101})

    assert too_small.status_code == 422
    assert too_large.status_code == 422
```

- [ ] **Step 2: Extend the existing OpenAPI test**

In `test_research_job_routes_document_response_models_in_openapi`, add this assertion after the existing route response model assertions and before `components = schema["components"]["schemas"]`:

```python
    list_parameters = schema["paths"]["/research/jobs"]["get"]["parameters"]
    assert list_parameters == [
        {
            "name": "status",
            "in": "query",
            "required": False,
            "schema": {
                "anyOf": [
                    {"enum": ["queued", "running", "succeeded", "failed", "cancelled"], "type": "string"},
                    {"type": "null"},
                ],
                "title": "Status",
            },
        },
        {
            "name": "limit",
            "in": "query",
            "required": False,
            "schema": {
                "default": 100,
                "maximum": 100,
                "minimum": 1,
                "title": "Limit",
                "type": "integer",
            },
        },
    ]
```

If FastAPI emits the `anyOf` entries for `status` in a different order, keep the same semantics but adjust the assertion to compare by `name` and inspect each parameter's schema separately.

- [ ] **Step 3: Run validation and OpenAPI tests and verify they pass**

Run:

```bash
python -m pytest tests/test_api.py::test_list_research_jobs_rejects_invalid_status tests/test_api.py::test_list_research_jobs_rejects_invalid_limits tests/test_api.py::test_research_job_routes_document_response_models_in_openapi -q
```

Expected: `3 passed`.

## Task 4: Update Architecture Documentation

**Files:**
- Modify: `docs/architecture.md`

- [ ] **Step 1: Update the API jobs description**

In `docs/architecture.md`, replace the sentence fragment in the `任务追踪` bullet that currently says:

```markdown
支持状态数量 summary、列出任务摘要、按 `job_id` 查询详情、取消尚未执行的 `queued` jobs，并返回 `created_at` / `started_at` / `finished_at` UTC 时间 metadata
```

with:

```markdown
支持状态数量 summary、按状态与数量上限列出任务摘要、按 `job_id` 查询详情、取消尚未执行的 `queued` jobs，并返回 `created_at` / `started_at` / `finished_at` UTC 时间 metadata
```

- [ ] **Step 2: Run focused API tests after documentation change**

Run:

```bash
python -m pytest tests/test_api.py -q
```

Expected: all API tests pass.

## Task 5: Full Verification And Commit

**Files:**
- Modify: `src/insight_graph/api.py`
- Modify: `tests/test_api.py`
- Modify: `docs/architecture.md`

- [ ] **Step 1: Run full tests**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass with no failures.

- [ ] **Step 2: Run lint**

Run:

```bash
python -m ruff check .
```

Expected: `All checks passed!`.

- [ ] **Step 3: Review diff**

Run:

```bash
git diff -- src/insight_graph/api.py tests/test_api.py docs/architecture.md
```

Expected: diff only contains `GET /research/jobs` query validation, list response filtering/limiting, related tests, and one architecture doc sentence update.

- [ ] **Step 4: Commit implementation**

Run:

```bash
git add src/insight_graph/api.py tests/test_api.py docs/architecture.md
git commit -m "feat: filter research job listings"
```

Expected: commit succeeds and includes only the three implementation files.

## Self-Review

- Spec coverage: status filter, limit validation, newest-first order, global queue positions, unchanged response model, invalid query `422`, OpenAPI docs, and docs update are covered.
- Placeholder scan: no placeholders, deferred tasks, or vague implementation steps remain.
- Type consistency: `ResearchJobStatusQuery`, `ResearchJobsLimitQuery`, `_jobs_list_response_locked(status, limit)`, and `list_research_jobs(status, limit)` are used consistently.
- Scope check: no offset, cursor, total count, persistence, auth, or WebSocket changes are included.
