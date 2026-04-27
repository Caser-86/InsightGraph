# Research Jobs API

The research jobs API is the non-blocking path for long-running research requests. It is a single-process MVP backed by the in-process repository documented in `docs/research-job-repository-contract.md`.

## Endpoints

- `POST /research/jobs` creates a queued job and returns `202`.
- `GET /research/jobs` lists retained jobs newest first.
- `GET /research/jobs/summary` returns status counts and active queued/running jobs.
- `GET /research/jobs/{job_id}` returns job detail.
- `POST /research/jobs/{job_id}/cancel` cancels a queued job.

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

Unknown jobs return `404`:

```json
{"detail":"Research job not found."}
```

## Cancel

```bash
curl -X POST http://127.0.0.1:8000/research/jobs/job-123/cancel
```

Only queued jobs are cancellable. Running or terminal jobs return `409`:

```json
{"detail":"Only queued research jobs can be cancelled."}
```

## Retention and persistence

- The in-memory repository retains the latest 100 terminal jobs: `succeeded`, `failed`, and `cancelled`.
- `queued` and `running` jobs are not pruned by terminal-job retention.
- `INSIGHT_GRAPH_RESEARCH_JOBS_PATH` enables opt-in JSON metadata persistence.
- On restart, unfinished persisted jobs become `failed` with `Research job did not complete before server restart.`
- Jobs are not automatically resumed or retried after restart.

## Runtime storage configuration

- Default: in-memory research job storage.
- `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=memory`: explicit in-memory storage.
- `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite`: use SQLite storage.
- `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/path/jobs.sqlite3`: required when backend is `sqlite`.
- `INSIGHT_GRAPH_RESEARCH_JOBS_PATH=/path/jobs.json`: existing JSON metadata path. With SQLite selected, this is only used as an optional import source during startup initialization.
