# API Jobs OpenAPI Polish Design

## Goal

Improve OpenAPI documentation for existing research job endpoints without changing runtime behavior.

## Scope

This is documentation-only API metadata polish for research job endpoints:

- `POST /research/jobs`
- `GET /research/jobs`
- `GET /research/jobs/summary`
- `GET /research/jobs/{job_id}`
- `POST /research/jobs/{job_id}/cancel`

The change should improve generated OpenAPI docs for humans and client generators. It must not change endpoint paths, HTTP methods, status codes, response bodies, response model names, query behavior, validation behavior, worker behavior, persistence behavior, or JSON store schema.

## Current Problem

Research job endpoints already expose response models, but the OpenAPI operation metadata is sparse. The generated schema identifies response models, but does not clearly explain:

- what each job endpoint does
- how queued/running/terminal job states behave
- what `status` and `limit` query parameters mean
- which error responses clients should expect
- example payload shapes for common responses

## Design

Add OpenAPI metadata directly to the existing FastAPI route decorators and query parameter definitions.

### Route Metadata

Each research job route should include:

- `tags=["research jobs"]`
- concise `summary`
- short `description`

The descriptions should document current behavior only. They should not promise retry, resume, authentication, pagination cursors, WebSocket updates, or cancellation of running jobs.

### Query Parameter Metadata

`GET /research/jobs` should document:

- `status`: optional filter for one public job status; omitted means all jobs
- `limit`: maximum returned jobs, `1..100`, default `100`

`count` in the response remains the returned count, not total matching jobs.

### Documented Error Responses

Use FastAPI route `responses` metadata to document existing error cases and examples:

- `POST /research/jobs`
  - `429`: `Too many active research jobs.`
  - `500`: `Research job store failed.`
- `GET /research/jobs/{job_id}`
  - `404`: `Research job not found.`
- `POST /research/jobs/{job_id}/cancel`
  - `404`: `Research job not found.`
  - `409`: `Only queued research jobs can be cancelled.`
  - `500`: `Research job store failed.`

The documented examples should match the existing FastAPI `HTTPException` body shape:

```json
{"detail": "Research job not found."}
```

Do not add a new error response model in this iteration.

### Response Examples

Add compact examples for successful job responses:

- created queued job
- job list with one queued job
- summary with queued/running groups
- succeeded job detail
- cancelled job detail

Examples should be small, deterministic, and use plausible timestamps. They are documentation examples only; they should not be used by runtime response builders.

## Non-Goals

- No runtime response changes.
- No new Pydantic models.
- No structured `ErrorResponse` model.
- No endpoint renaming.
- No auth documentation.
- No pagination cursor or total count additions.
- No `/health` or synchronous `/research` polish in this iteration.
- No changes to research job worker behavior.

## Testing

Update OpenAPI tests in `tests/test_api.py` to assert:

- all research job operations share the `research jobs` tag
- summaries/descriptions exist for the job operations
- `status` and `limit` parameter descriptions are present
- documented error response examples exist for 404, 409, 429, and 500 where applicable
- existing response model references remain unchanged
- optional omitted fields remain non-nullable in the schema

Run:

```bash
python -m pytest tests/test_api.py::test_research_job_routes_document_response_models_in_openapi -q
python -m pytest tests/test_api.py -q
python -m pytest -q
python -m ruff check .
```

## Self-Review

- Scope is documentation-only.
- Public runtime API behavior is unchanged.
- Error examples match existing `HTTPException` response bodies.
- No placeholders remain.
- Implementation can be done in one focused plan.
