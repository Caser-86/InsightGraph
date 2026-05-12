# Research Jobs And Memory API

This is the canonical reference for InsightGraph asynchronous job execution,
restart/resume behavior, report export, and memory management.

## Authentication

If `INSIGHT_GRAPH_API_KEY` is configured, all endpoints below require either:

- `Authorization: Bearer <key>`
- `X-API-Key: <key>`

`/health` remains public.

## Job Endpoints

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

## Memory Endpoints

- `GET /memory`
- `POST /memory/search`
- `DELETE /memory/{memory_id}`

## Create Job

```bash
curl -X POST http://127.0.0.1:8000/research/jobs \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare AI coding agents","preset":"live-research"}'
```

Response:

```json
{
  "job_id": "job-123",
  "status": "queued",
  "created_at": "2026-04-27T10:00:00Z"
}
```

If `queued + running` reaches the active cap, create returns `429`.

## List Jobs

```bash
curl "http://127.0.0.1:8000/research/jobs?status=queued&limit=20"
```

Rules:

- `status` is optional
- `limit` must be between `1` and `100`
- jobs are returned newest first
- list payloads do not include `result` or `error`

## Summary

`GET /research/jobs/summary` returns:

- status counts
- `active_count`
- `active_limit`
- queued job summaries
- running job summaries

## Detail

`GET /research/jobs/{job_id}` returns one full job view.

Depending on state, the payload may include:

- `queue_position`
- `started_at`
- `finished_at`
- `result`
- `error`
- `events`
- `progress_stage`
- `progress_percent`
- `progress_steps`
- `runtime_seconds`
- `tool_call_count`
- `llm_call_count`

Unknown jobs return:

```json
{"detail":"Research job not found."}
```

## Cancel

```bash
curl -X POST http://127.0.0.1:8000/research/jobs/job-123/cancel
```

Queued and running jobs are cancellable. Terminal jobs return `409`:

```json
{"detail":"Only queued or running research jobs can be cancelled."}
```

Successful cancel returns the normal job detail shape with `status:
"cancelled"`.

## Retry

```bash
curl -X POST http://127.0.0.1:8000/research/jobs/job-123/retry
```

Only `failed` and `cancelled` jobs are retryable. Retry creates a new queued
job with the same query and preset.

Non-retryable jobs return:

```json
{"detail":"Only failed or cancelled research jobs can be retried."}
```

## Delete

```bash
curl -X DELETE http://127.0.0.1:8000/research/jobs/job-123
```

Delete is allowed only for terminal jobs. Active jobs return `409`.

## Report Export

```bash
curl http://127.0.0.1:8000/research/jobs/job-123/report.md
curl http://127.0.0.1:8000/research/jobs/job-123/report.html
```

Jobs without an available report return:

```json
{"detail":"Research job report is not available."}
```

## WebSocket Stream

```text
ws://127.0.0.1:8000/research/jobs/job-123/stream
```

The stream sends safe JSON snapshots and safe event records. It does not send
prompts, completions, raw provider payloads, request bodies, headers, or API
keys.

Possible event types include:

- `job_snapshot`
- `stage_started`
- `stage_finished`
- `tool_call`
- `llm_call`
- `report_ready`
- `resumed_from_checkpoint`

## Retention And Cleanup

Terminal job retention applies only to `succeeded`, `failed`, and `cancelled`
jobs. This terminal job retention rule never deletes queued or running jobs.

- Count-based retention prunes the oldest terminal jobs.
- Time-based cleanup is opt-in via
  `INSIGHT_GRAPH_RESEARCH_JOBS_TERMINAL_RETENTION_DAYS`.
- SQLite cleanup deletes matching terminal rows from the `research_jobs` table.
- artifact retention is external: report downloads depend on retained job
  records, but CI artifacts and external storage are outside research job
  cleanup.

## Restart And Resume Smoke Path

SQLite jobs can resume after process restart when startup worker processing is
enabled.

- Set `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite`
- Set `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/path/jobs.sqlite3`
- Set `INSIGHT_GRAPH_RESEARCH_JOBS_STARTUP_WORKER=1`
- Set `INSIGHT_GRAPH_CHECKPOINT_RESUME=1` if you want the workflow to reuse the
  job ID as checkpoint `run_id`

Rules:

- queued jobs stay queued until a worker claim
- expired running jobs are requeued through worker lease claim
- checkpoint resume can continue from the latest stored checkpoint
- worker claim ownership prevents cross-worker terminal writes

This restart/resume smoke path covers queued jobs, expired running jobs,
checkpoint resume routing, and worker claim behavior.

## Runtime Storage Configuration

- `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=memory`
- `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite`
- `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/path/jobs.sqlite3`
- `INSIGHT_GRAPH_RESEARCH_JOBS_PATH=/path/jobs.json`

JSON metadata persistence is single-process only. SQLite is the durable
multi-process-safe job metadata path.

## Memory API

### List Memory Records

```bash
curl http://127.0.0.1:8000/memory
```

### Search Memory Records

```bash
curl -X POST http://127.0.0.1:8000/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Xiaomi SU7 deliveries", "limit": 5}'
```

### Delete One Memory Record

```bash
curl -X DELETE http://127.0.0.1:8000/memory/memory-123
```

When `INSIGHT_GRAPH_MEMORY_WRITEBACK=1`, successful reports can write summary,
entity, supported-claim, reference, and source-reliability records into the
configured memory backend.
