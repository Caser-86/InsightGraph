# Research Jobs API

The research jobs API is the non-blocking path for long-running research requests. It uses the repository contract documented in `docs/research-job-repository-contract.md` and supports in-memory storage by default, opt-in JSON metadata persistence, and opt-in SQLite storage with internal worker leasing.

If `INSIGHT_GRAPH_API_KEY` is configured, all research job endpoints require `Authorization: Bearer <key>` or `X-API-Key: <key>`. `/health` remains public.

## Endpoints

- `POST /research/jobs` creates a queued job and returns `202`.
- `GET /research/jobs` lists retained jobs newest first.
- `GET /research/jobs/summary` returns status counts and active queued/running jobs.
- `GET /research/jobs/{job_id}` returns job detail.
- `WS /research/jobs/{job_id}/stream` streams safe job snapshots for dashboard updates.
- `GET /research/jobs/{job_id}/report.md` downloads a completed Markdown report.
- `GET /research/jobs/{job_id}/report.html` downloads an escaped HTML report.
- `POST /research/jobs/{job_id}/cancel` cancels a queued job.
- `POST /research/jobs/{job_id}/retry` creates a new queued job from a failed or cancelled job.

## Create job

```bash
curl -X POST http://127.0.0.1:8000/research/jobs \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor, OpenCode, and GitHub Copilot"}'
```

Response:

```json
{
  "job_id": "job-123",
  "status": "queued",
  "created_at": "2026-04-27T10:00:00Z"
}
```

If `queued + running` reaches the active cap, create returns `429`:

```json
{"detail":"Too many active research jobs."}
```

## List jobs

```bash
curl "http://127.0.0.1:8000/research/jobs?status=queued&limit=2"
```

- `status` is optional and can be `queued`, `running`, `succeeded`, `failed`, or `cancelled`.
- `limit` is optional and must be between `1` and `100`.
- Jobs are returned newest first by `created_order`.
- List responses contain summaries only; they do not include `result` or `error`.

Example:

```json
{
  "jobs": [
    {
      "job_id": "job-123",
      "status": "queued",
      "query": "Compare AI coding agents",
      "preset": "offline",
      "created_at": "2026-04-27T10:00:00Z",
      "queue_position": 1
    }
  ],
  "count": 1
}
```

## Summary

```bash
curl http://127.0.0.1:8000/research/jobs/summary
```

Summary includes all status counts, `active_count`, `active_limit`, queued job summaries, and running job summaries. `queue_position` is 1-based and dynamic for queued jobs only.

```json
{
  "counts": {
    "queued": 1,
    "running": 1,
    "succeeded": 0,
    "failed": 0,
    "cancelled": 0,
    "total": 2
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
      "queue_position": 1
    }
  ],
  "running_jobs": [
    {
      "job_id": "job-456",
      "status": "running",
      "query": "Analyze market signals",
      "preset": "offline",
      "created_at": "2026-04-27T10:01:00Z",
      "started_at": "2026-04-27T10:01:01Z"
    }
  ]
}
```

## Detail

```bash
curl http://127.0.0.1:8000/research/jobs/job-123
```

- `queued` includes `queue_position`.
- `running` includes `started_at`.
- `succeeded` includes `result`.
- `failed` includes safe `error` only.
- `cancelled` includes `finished_at`.
- Detail responses include derived progress metadata: `progress_stage`, `progress_percent`, `progress_steps`, `runtime_seconds`, `tool_call_count`, and `llm_call_count`.
- Detail responses include bounded safe `events` when available. Job list and summary responses omit events to keep those payloads compact.
- Progress is derived from stored job state, result logs, and safe stage events.

```json
{
  "job_id": "job-123",
  "status": "running",
  "events": [
    {"type":"stage_started","stage":"planner","sequence":1}
  ]
}
```

Unknown jobs return `404`:

```json
{"detail":"Research job not found."}
```

## WebSocket stream

```text
ws://127.0.0.1:8000/research/jobs/job-123/stream
```

The stream sends safe JSON events using the same job detail shape as REST,
including derived progress fields. It does not stream prompts, completions, raw
provider responses, headers, request bodies, or API keys.

```json
{
  "type": "job_snapshot",
  "job": {
    "job_id": "job-123",
    "status": "running",
    "progress_stage": "planner",
    "progress_percent": 20
  }
}
```

While a worker runs in the same process, the stream may also include safe execution
events:

```json
{"type":"stage_started","stage":"planner","sequence":1}
{"type":"stage_finished","stage":"collector","sequence":4}
{"type":"tool_call","record":{"tool_name":"mock_search","success":true},"sequence":5}
{"type":"llm_call","record":{"stage":"analyst","model":"...","success":true},"sequence":6}
{"type":"report_ready","sequence":10}
```

Event history is bounded and persisted with retained job details. On process restart,
or when connecting to a different process than the one executing the job, clients may
still receive replayed persisted events, but not live cross-process pub/sub updates.
When cached stage events are available in the same process, snapshot progress fields
derive from those events, so `progress_stage`, `progress_percent`, and
`progress_steps` show the active Planner, Collector, Analyst, Critic, or Reporter
stage instead of the generic running fallback. If memory cache is empty, persisted
stage events are used as a fallback.

Unknown jobs send an error event and close:

```json
{"type":"error","detail":"Research job not found."}
```

If `INSIGHT_GRAPH_API_KEY` is configured, browser clients pass the key as a query
parameter because standard browser WebSocket APIs cannot set custom headers:

```text
ws://127.0.0.1:8000/research/jobs/job-123/stream?api_key=demo-key
```

## Report export

```bash
curl http://127.0.0.1:8000/research/jobs/job-123/report.md
curl http://127.0.0.1:8000/research/jobs/job-123/report.html
```

Report export endpoints require the same API key headers as other research job
endpoints when `INSIGHT_GRAPH_API_KEY` is configured. They return completed report
content only. Jobs without an available report return `409`:

```json
{"detail":"Research job report is not available."}
```

## Cancel

```bash
curl -X POST http://127.0.0.1:8000/research/jobs/job-123/cancel
```

Only queued jobs are cancellable. Running or terminal jobs return `409`:

```json
{"detail":"Only queued research jobs can be cancelled."}
```

## Retry

```bash
curl -X POST http://127.0.0.1:8000/research/jobs/job-123/retry
```

Only `failed` and `cancelled` jobs are retryable. Retry creates a new queued job with the same query and preset; the source job is unchanged.

Successful retry returns `202` with a normal create response:

```json
{
  "job_id": "job-789",
  "status": "queued",
  "created_at": "2026-04-27T10:05:00Z"
}
```

Unknown source jobs return `404`:

```json
{"detail":"Research job not found."}
```

Non-retryable jobs return `409`:

```json
{"detail":"Only failed or cancelled research jobs can be retried."}
```

If `queued + running` reaches the active cap, retry returns `429`:

```json
{"detail":"Too many active research jobs."}
```

If configured storage fails while creating the retry job, retry returns `500`:

```json
{"detail":"Research job store failed."}
```

## Retention and persistence

- The in-memory repository retains the latest 100 terminal jobs: `succeeded`, `failed`, and `cancelled`.
- `queued` and `running` jobs are not pruned by terminal-job retention.
- `INSIGHT_GRAPH_RESEARCH_JOBS_PATH` enables opt-in JSON metadata persistence.
- With JSON metadata persistence, unfinished persisted jobs become `failed` with `Research job did not complete before server restart.`
- With SQLite storage, queued jobs remain queued and expired running jobs are requeued through internal worker lease claim.
- Workflow execution is not resumed in-place after restart, and jobs are not automatically retried after terminal failure.

## Runtime storage configuration

- Default: in-memory research job storage.
- `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=memory`: explicit in-memory storage.
- `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite`: use SQLite storage.
- `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/path/jobs.sqlite3`: required when backend is `sqlite`.
- `INSIGHT_GRAPH_RESEARCH_JOBS_PATH=/path/jobs.json`: existing JSON metadata path. With SQLite selected, this is only used as an optional import source during startup initialization.
