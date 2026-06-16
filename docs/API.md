# InsightGraph API Reference

This file is the high-level API entry point. It explains the public API surface
and points to the canonical job lifecycle document.

## Canonical Job API Reference

For current async job lifecycle, cancel/retry semantics, restart/resume
behavior, report export, and memory endpoints, use:

- `docs/research-jobs-api.md`

If examples in this file differ from that document, prefer
`docs/research-jobs-api.md`.

## Base Endpoints

### Public

- `GET /health`
- `GET /dashboard`
- `GET /docs`
- `GET /redoc`
- `GET /openapi.json`

### Protected When `INSIGHT_GRAPH_API_KEY` Is Set

- `POST /research`
- `GET /memory`
- `POST /memory/search`
- `DELETE /memory/{memory_id}`
- `POST /research/jobs`
- `GET /research/jobs`
- `GET /research/jobs/summary`
- `GET /research/jobs/{job_id}`
- `POST /research/jobs/{job_id}/cancel`
- `POST /research/jobs/{job_id}/retry`
- `DELETE /research/jobs/{job_id}`
- `GET /research/jobs/{job_id}/report.md`
- `GET /research/jobs/{job_id}/report.html`
- `WS /research/jobs/{job_id}/stream`

## Authentication

Use either:

- `Authorization: Bearer <key>`
- `X-API-Key: <key>`

Example:

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H "Authorization: Bearer $INSIGHT_GRAPH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor and GitHub Copilot"}'
```

## Synchronous Research

`POST /research` is the fastest way to run a single workflow and get the final
report payload directly.

Typical request:

```json
{
  "query": "Compare Cursor and GitHub Copilot",
  "preset": "offline"
}
```

Supported high-level request fields:

- `query`
- `preset`
- `report_intensity`
- `single_entity_detail_mode`
- `relevance_judge`
- `fetch_rendered`
- `search_provider`
- `web_search_mode`

Typical response fields:

- `report_markdown`
- `findings`
- `competitive_matrix`
- `tool_call_log`
- `llm_call_log`
- `evidence_pool`
- `quality`
- `quality_cards`
- `runtime_diagnostics`

## Memory API

The memory API is a management surface for long-term memory records.

### List

```bash
curl http://127.0.0.1:8000/memory
```

### Search

```bash
curl -X POST http://127.0.0.1:8000/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Xiaomi EV supply chain", "limit": 5}'
```

### Delete

```bash
curl -X DELETE http://127.0.0.1:8000/memory/memory-123
```

## Dashboard

Open:

```text
http://127.0.0.1:8000/dashboard
```

The dashboard is a zero-build UI for:

- submitting jobs
- monitoring status and events
- inspecting report quality cards
- viewing evidence and citation support
- exporting Markdown and HTML reports

## Error Model

Most API failures return a safe JSON object:

```json
{
  "detail": "Human-readable error message."
}
```

Common status codes:

- `401` invalid or missing API key
- `404` resource not found
- `409` invalid state transition
- `429` active job limit reached
- `500` store or workflow failure
