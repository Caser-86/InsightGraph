# Dashboard WebSocket Stream Design

## Goal

Match the reference project's FastAPI REST + WebSocket streaming architecture at MVP scale by adding a job snapshot stream for the existing static dashboard.

## Scope

In scope:

- Add `WebSocket /research/jobs/{job_id}/stream`.
- Stream safe `job_snapshot` events using existing job detail shape and derived progress fields.
- Keep existing REST endpoints as the source of truth for creating, listing, polling, and exporting jobs.
- Dashboard connects to WebSocket for the selected job and updates the UI from snapshots.
- Keep polling fallback when WebSocket is unavailable or closes.
- Support API-key-protected servers through a WebSocket query parameter because browser WebSocket cannot set custom request headers.

Out of scope:

- WebSocket command/control messages from client to server.
- Per-node LangGraph event persistence.
- PostgreSQL checkpoint or pgvector memory changes.
- Streaming raw prompts, completions, headers, request bodies, or API keys.

## WebSocket Protocol

Endpoint:

```text
WS /research/jobs/{job_id}/stream
```

Auth:

- If `INSIGHT_GRAPH_API_KEY` is unset, the stream is public, matching REST job routes.
- If configured, clients pass `?api_key=<key>`.
- Invalid or missing key closes the connection with policy violation code `1008`.

Events are JSON objects:

```json
{
  "type": "job_snapshot",
  "job": {
    "job_id": "...",
    "status": "running",
    "progress_stage": "planner",
    "progress_percent": 20
  }
}
```

Terminal jobs send a final snapshot and then close normally. Unknown jobs send an `error` event with `Research job not found.` and then close normally.

## Dashboard Behavior

- On selected job change, close any existing WebSocket and open a stream for the new job.
- Build the WebSocket URL from the current page protocol/host.
- If an API key is present, append `api_key` in the query string.
- On each `job_snapshot`, update `state.detail`, render job details, and keep metric/list refresh on the existing polling interval.
- If WebSocket errors or closes before a terminal snapshot, fall back to polling.
- Keep the existing auto-refresh toggle; disabling auto-refresh disables both polling and stream reconnection.

## Testing

Add tests for:

- A known queued job streams a `job_snapshot` event.
- A missing job streams an `error` event.
- A configured API key rejects missing WebSocket auth.
- A configured API key accepts the `api_key` query parameter.
- Dashboard HTML contains WebSocket stream markers.

Verification:

- `python -m pytest tests/test_api.py -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
