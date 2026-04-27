# API Jobs List Filtering Design

## Goal

Add bounded query controls to `GET /research/jobs` so clients can request the most relevant job summaries without pulling the full in-memory list every time.

## Scope

This change only affects the research jobs list endpoint. It does not change job creation, detail, cancellation, summary, execution, retention, persistence, authentication, or streaming behavior.

## API Contract

`GET /research/jobs` accepts two optional query parameters:

- `status`: one of `queued`, `running`, `succeeded`, `failed`, or `cancelled`.
- `limit`: integer from `1` through `100`, default `100`.

If `status` is omitted, the endpoint lists jobs across all statuses. If `status` is provided, the endpoint lists only jobs with that exact status. Invalid `status` or `limit` values return FastAPI validation errors with HTTP `422`.

The response model stays `ResearchJobsListResponse`:

```json
{
  "jobs": [],
  "count": 0
}
```

`count` is the number of jobs returned after filtering and limiting. This design intentionally does not add `total`, `offset`, `next_cursor`, or pagination metadata, because the current job store is a single-process in-memory MVP and the list can change as jobs start, finish, cancel, or prune.

## Ordering And Queue Positions

The endpoint keeps the existing newest-first ordering by `created_order` descending. Filtering happens before limiting so `GET /research/jobs?status=queued&limit=2` returns the two newest queued jobs.

`queue_position` remains a global position in the full queued job set. It is not renumbered within a filtered or limited response.

## Implementation

Use FastAPI query validation on `list_research_jobs`:

- `status` should be constrained to the existing public job statuses.
- `limit` should use `ge=1` and `le=100`.

Update `_jobs_list_response_locked` to accept `status` and `limit`. The function should:

1. Sort all jobs newest-first, preserving current behavior.
2. Filter by `status` when provided.
3. Slice to `limit`.
4. Compute queue positions from the full queued set.
5. Return summaries and `count` for the returned list.

No new response model is required.

## Testing

Add API tests for:

- Default list behavior still returns newest-first job summaries with existing shape.
- `status` filter returns only matching jobs.
- `limit` returns only the newest N matching jobs.
- `queue_position` remains global after filtering and limiting.
- Invalid `status` returns `422`.
- Invalid `limit` below `1` and above `100` returns `422`.
- OpenAPI documents the `status` and `limit` query parameters.

Run focused API tests, full pytest, and ruff.

## Non-Goals

- No offset pagination.
- No cursor pagination.
- No total count across all matching jobs.
- No changes to retained job limits.
- No persistence, auth, or WebSocket behavior.

## Self-Review

- No placeholders remain.
- The design is limited to one endpoint and one response shape.
- Validation behavior is explicit: invalid query parameters return `422`.
- The `count` meaning is explicit and does not imply future pagination metadata.
