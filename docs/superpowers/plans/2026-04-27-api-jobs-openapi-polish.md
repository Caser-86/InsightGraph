# API Jobs OpenAPI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add documentation-only OpenAPI metadata to existing research job endpoints without changing runtime behavior.

**Architecture:** Keep all runtime logic in `src/insight_graph/api.py` unchanged. Add small OpenAPI metadata constants near the response models, wire them into existing FastAPI route decorators and `Query` annotations, and extend the existing OpenAPI schema test.

**Tech Stack:** Python 3.11+, FastAPI route metadata, Pydantic response models, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/api.py`: add OpenAPI examples/error metadata constants, add route `tags`/`summary`/`description`/`responses`, and add query parameter descriptions.
- Modify `tests/test_api.py`: extend `test_research_job_routes_document_response_models_in_openapi` to assert job route tags, descriptions, query parameter docs, error examples, and success examples while preserving current response model assertions.

## Task 1: Add Failing OpenAPI Metadata Tests

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Extend the existing OpenAPI schema test**

Replace `test_research_job_routes_document_response_models_in_openapi` with:

```python
def test_research_job_routes_document_response_models_in_openapi() -> None:
    api_module.app.openapi_schema = None

    schema = api_module.app.openapi()
    paths = schema["paths"]
    create_operation = paths["/research/jobs"]["post"]
    list_operation = paths["/research/jobs"]["get"]
    summary_operation = paths["/research/jobs/summary"]["get"]
    detail_operation = paths["/research/jobs/{job_id}"]["get"]
    cancel_operation = paths["/research/jobs/{job_id}/cancel"]["post"]
    job_operations = [
        create_operation,
        list_operation,
        summary_operation,
        detail_operation,
        cancel_operation,
    ]

    for operation in job_operations:
        assert operation["tags"] == ["research jobs"]
        assert operation["summary"]
        assert operation["description"]

    assert create_operation["responses"]["202"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ResearchJobCreateResponse"}
    assert list_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ResearchJobsListResponse"}
    assert summary_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ResearchJobsSummaryResponse"}
    assert detail_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ResearchJobDetailResponse"}
    assert cancel_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ResearchJobDetailResponse"}

    assert create_operation["responses"]["202"]["content"]["application/json"][
        "example"
    ] == {
        "job_id": "job-123",
        "status": "queued",
        "created_at": "2026-04-27T10:00:00Z",
    }
    assert list_operation["responses"]["200"]["content"]["application/json"][
        "example"
    ] == {
        "jobs": [
            {
                "job_id": "job-123",
                "status": "queued",
                "query": "Compare AI coding agents",
                "preset": "offline",
                "created_at": "2026-04-27T10:00:00Z",
                "queue_position": 1,
            }
        ],
        "count": 1,
    }
    assert summary_operation["responses"]["200"]["content"]["application/json"][
        "example"
    ] == {
        "counts": {
            "queued": 1,
            "running": 1,
            "succeeded": 0,
            "failed": 0,
            "cancelled": 0,
            "total": 2,
        },
        "active_count": 2,
        "active_limit": 100,
        "queued_jobs": [
            {
                "job_id": "job-123",
                "status": "queued",
                "query": "Compare AI coding agents",
                "preset": "offline",
                "created_at": "2026-04-27T10:00:00Z",
                "queue_position": 1,
            }
        ],
        "running_jobs": [
            {
                "job_id": "job-456",
                "status": "running",
                "query": "Analyze market signals",
                "preset": "offline",
                "created_at": "2026-04-27T10:01:00Z",
                "started_at": "2026-04-27T10:01:01Z",
            }
        ],
    }
    assert detail_operation["responses"]["200"]["content"]["application/json"][
        "example"
    ] == {
        "job_id": "job-789",
        "status": "succeeded",
        "created_at": "2026-04-27T10:02:00Z",
        "started_at": "2026-04-27T10:02:01Z",
        "finished_at": "2026-04-27T10:02:05Z",
        "result": {"report_markdown": "# InsightGraph Research Report\n"},
    }
    assert cancel_operation["responses"]["200"]["content"]["application/json"][
        "example"
    ] == {
        "job_id": "job-123",
        "status": "cancelled",
        "created_at": "2026-04-27T10:00:00Z",
        "finished_at": "2026-04-27T10:00:10Z",
    }

    assert create_operation["responses"]["429"]["content"]["application/json"][
        "example"
    ] == {"detail": "Too many active research jobs."}
    assert create_operation["responses"]["500"]["content"]["application/json"][
        "example"
    ] == {"detail": "Research job store failed."}
    assert detail_operation["responses"]["404"]["content"]["application/json"][
        "example"
    ] == {"detail": "Research job not found."}
    assert cancel_operation["responses"]["404"]["content"]["application/json"][
        "example"
    ] == {"detail": "Research job not found."}
    assert cancel_operation["responses"]["409"]["content"]["application/json"][
        "example"
    ] == {"detail": "Only queued research jobs can be cancelled."}
    assert cancel_operation["responses"]["500"]["content"]["application/json"][
        "example"
    ] == {"detail": "Research job store failed."}

    list_parameters = list_operation["parameters"]
    assert list_parameters == [
        {
            "name": "status",
            "in": "query",
            "required": False,
            "description": "Filter jobs by status. Omit to return all retained jobs.",
            "schema": {
                "anyOf": [
                    {
                        "enum": [
                            "queued",
                            "running",
                            "succeeded",
                            "failed",
                            "cancelled",
                        ],
                        "type": "string",
                    },
                    {"type": "null"},
                ],
                "title": "Status",
            },
        },
        {
            "name": "limit",
            "in": "query",
            "required": False,
            "description": "Maximum number of jobs to return. The response count is the returned count, not a total.",
            "schema": {
                "default": 100,
                "maximum": 100,
                "minimum": 1,
                "title": "Limit",
                "type": "integer",
            },
        },
    ]

    components = schema["components"]["schemas"]
    assert components["ResearchJobCreateResponse"]["required"] == [
        "job_id",
        "status",
        "created_at",
    ]
    assert components["ResearchJobSummary"]["required"] == [
        "job_id",
        "status",
        "query",
        "preset",
        "created_at",
    ]
    assert components["ResearchJobsListResponse"]["properties"]["jobs"] == {
        "items": {"$ref": "#/components/schemas/ResearchJobSummary"},
        "title": "Jobs",
        "type": "array",
    }
    assert components["ResearchJobsSummaryResponse"]["properties"]["queued_jobs"] == {
        "items": {"$ref": "#/components/schemas/ResearchJobSummary"},
        "title": "Queued Jobs",
        "type": "array",
    }
    for schema_name, optional_fields in {
        "ResearchJobSummary": ["started_at", "finished_at", "queue_position"],
        "ResearchJobDetailResponse": [
            "started_at",
            "finished_at",
            "queue_position",
            "result",
            "error",
        ],
    }.items():
        properties = components[schema_name]["properties"]
        for field_name in optional_fields:
            assert {"type": "null"} not in properties[field_name].get("anyOf", [])
```

- [ ] **Step 2: Run the OpenAPI schema test and verify red**

Run:

```bash
python -m pytest tests/test_api.py::test_research_job_routes_document_response_models_in_openapi -q
```

Expected: FAIL because research job operations do not yet have explicit `research jobs` tags, custom summaries/descriptions, examples, or parameter descriptions.

## Task 2: Add OpenAPI Metadata Constants And Route Metadata

**Files:**
- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Replace query type aliases with documented `Query` annotations**

Replace:

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

with:

```python
ResearchJobStatusQuery = Annotated[
    Literal[
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
    ]
    | None,
    Query(description="Filter jobs by status. Omit to return all retained jobs."),
]
ResearchJobsLimitQuery = Annotated[
    int,
    Query(
        ge=1,
        le=100,
        description="Maximum number of jobs to return. The response count is the returned count, not a total.",
    ),
]
```

- [ ] **Step 2: Add OpenAPI metadata constants after response model classes**

Insert after `ResearchJobsSummaryResponse`:

```python
_RESEARCH_JOBS_TAG = "research jobs"
_RESEARCH_JOB_NOT_FOUND_RESPONSE = {
    "description": "Research job not found.",
    "content": {"application/json": {"example": {"detail": "Research job not found."}}},
}
_RESEARCH_JOB_STORE_FAILED_RESPONSE = {
    "description": "Research job store failed.",
    "content": {
        "application/json": {"example": {"detail": "Research job store failed."}}
    },
}
_TOO_MANY_ACTIVE_RESEARCH_JOBS_RESPONSE = {
    "description": "Too many active research jobs.",
    "content": {
        "application/json": {"example": {"detail": "Too many active research jobs."}}
    },
}
_RESEARCH_JOB_CANCEL_CONFLICT_RESPONSE = {
    "description": "Only queued research jobs can be cancelled.",
    "content": {
        "application/json": {
            "example": {"detail": "Only queued research jobs can be cancelled."}
        }
    },
}
_RESEARCH_JOB_CREATE_EXAMPLE = {
    "job_id": "job-123",
    "status": "queued",
    "created_at": "2026-04-27T10:00:00Z",
}
_RESEARCH_JOB_LIST_EXAMPLE = {
    "jobs": [
        {
            "job_id": "job-123",
            "status": "queued",
            "query": "Compare AI coding agents",
            "preset": "offline",
            "created_at": "2026-04-27T10:00:00Z",
            "queue_position": 1,
        }
    ],
    "count": 1,
}
_RESEARCH_JOBS_SUMMARY_EXAMPLE = {
    "counts": {
        "queued": 1,
        "running": 1,
        "succeeded": 0,
        "failed": 0,
        "cancelled": 0,
        "total": 2,
    },
    "active_count": 2,
    "active_limit": 100,
    "queued_jobs": [
        {
            "job_id": "job-123",
            "status": "queued",
            "query": "Compare AI coding agents",
            "preset": "offline",
            "created_at": "2026-04-27T10:00:00Z",
            "queue_position": 1,
        }
    ],
    "running_jobs": [
        {
            "job_id": "job-456",
            "status": "running",
            "query": "Analyze market signals",
            "preset": "offline",
            "created_at": "2026-04-27T10:01:00Z",
            "started_at": "2026-04-27T10:01:01Z",
        }
    ],
}
_RESEARCH_JOB_DETAIL_EXAMPLE = {
    "job_id": "job-789",
    "status": "succeeded",
    "created_at": "2026-04-27T10:02:00Z",
    "started_at": "2026-04-27T10:02:01Z",
    "finished_at": "2026-04-27T10:02:05Z",
    "result": {"report_markdown": "# InsightGraph Research Report\n"},
}
_RESEARCH_JOB_CANCEL_EXAMPLE = {
    "job_id": "job-123",
    "status": "cancelled",
    "created_at": "2026-04-27T10:00:00Z",
    "finished_at": "2026-04-27T10:00:10Z",
}
```

- [ ] **Step 3: Add metadata to `POST /research/jobs`**

Update the decorator to:

```python
@router.post(
    "/research/jobs",
    status_code=202,
    response_model=ResearchJobCreateResponse,
    response_model_exclude_none=True,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Create research job",
    description=(
        "Queue a research workflow for background execution. Jobs start as queued and "
        "can be inspected with the job detail endpoint."
    ),
    responses={
        202: {"content": {"application/json": {"example": _RESEARCH_JOB_CREATE_EXAMPLE}}},
        429: _TOO_MANY_ACTIVE_RESEARCH_JOBS_RESPONSE,
        500: _RESEARCH_JOB_STORE_FAILED_RESPONSE,
    },
)
```

- [ ] **Step 4: Add metadata to `GET /research/jobs` and simplify function annotation**

Update the decorator and signature to:

```python
@router.get(
    "/research/jobs",
    response_model=ResearchJobsListResponse,
    response_model_exclude_none=True,
    tags=[_RESEARCH_JOBS_TAG],
    summary="List research jobs",
    description=(
        "Return retained research jobs ordered newest first. Optional status filtering "
        "does not change queued job positions."
    ),
    responses={
        200: {"content": {"application/json": {"example": _RESEARCH_JOB_LIST_EXAMPLE}}},
    },
)
def list_research_jobs(
    status: ResearchJobStatusQuery = None,
    limit: ResearchJobsLimitQuery = 100,
) -> dict[str, Any]:
```

- [ ] **Step 5: Add metadata to `GET /research/jobs/summary`**

Update the decorator to:

```python
@router.get(
    "/research/jobs/summary",
    response_model=ResearchJobsSummaryResponse,
    response_model_exclude_none=True,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Summarize research jobs",
    description=(
        "Return job counts plus queued and running job summaries for monitoring active work."
    ),
    responses={
        200: {
            "content": {"application/json": {"example": _RESEARCH_JOBS_SUMMARY_EXAMPLE}}
        },
    },
)
```

- [ ] **Step 6: Add metadata to `POST /research/jobs/{job_id}/cancel`**

Update the decorator to:

```python
@router.post(
    "/research/jobs/{job_id}/cancel",
    response_model=ResearchJobDetailResponse,
    response_model_exclude_none=True,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Cancel queued research job",
    description=(
        "Cancel a queued research job. Running and terminal jobs are not cancellable."
    ),
    responses={
        200: {"content": {"application/json": {"example": _RESEARCH_JOB_CANCEL_EXAMPLE}}},
        404: _RESEARCH_JOB_NOT_FOUND_RESPONSE,
        409: _RESEARCH_JOB_CANCEL_CONFLICT_RESPONSE,
        500: _RESEARCH_JOB_STORE_FAILED_RESPONSE,
    },
)
```

- [ ] **Step 7: Add metadata to `GET /research/jobs/{job_id}`**

Update the decorator to:

```python
@router.get(
    "/research/jobs/{job_id}",
    response_model=ResearchJobDetailResponse,
    response_model_exclude_none=True,
    tags=[_RESEARCH_JOBS_TAG],
    summary="Get research job",
    description=(
        "Return one research job. Succeeded jobs include result, failed jobs include "
        "a safe error message, and queued jobs include queue position."
    ),
    responses={
        200: {"content": {"application/json": {"example": _RESEARCH_JOB_DETAIL_EXAMPLE}}},
        404: _RESEARCH_JOB_NOT_FOUND_RESPONSE,
    },
)
```

- [ ] **Step 8: Run the OpenAPI schema test and verify green**

Run:

```bash
python -m pytest tests/test_api.py::test_research_job_routes_document_response_models_in_openapi -q
```

Expected: `1 passed`.

## Task 3: Verify No Runtime Regression

**Files:**
- Test: `tests/test_api.py`
- Test: full repository

- [ ] **Step 1: Run API tests**

Run:

```bash
python -m pytest tests/test_api.py -q
```

Expected: all API tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass with the existing skipped test count unchanged.

- [ ] **Step 3: Run linter**

Run:

```bash
python -m ruff check .
```

Expected: `All checks passed!`.

## Task 4: Commit Implementation

**Files:**
- Modify: `src/insight_graph/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Review diff**

Run:

```bash
git diff -- src/insight_graph/api.py tests/test_api.py
```

Expected: diff only contains OpenAPI metadata constants, route/query metadata, and schema test assertions.

- [ ] **Step 2: Commit implementation**

Run:

```bash
git add src/insight_graph/api.py tests/test_api.py
git commit -m "docs: polish research jobs OpenAPI metadata"
```

Expected: commit succeeds.

## Self-Review

- Spec coverage: route metadata, query parameter descriptions, success examples, documented error examples, and existing schema preservation are covered.
- Placeholder scan: no placeholder steps or deferred implementation notes remain.
- Type consistency: `ResearchJobStatusQuery` remains the public status literal, now wrapped in `Annotated`; route response models remain unchanged.
- Runtime behavior stays unchanged because only FastAPI OpenAPI metadata and tests change.
