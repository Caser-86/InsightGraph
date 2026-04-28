# Dashboard v2 Progress and Export Design

## Goal

Add a more demo-friendly dashboard experience by showing a workflow progress timeline and providing downloadable Markdown/HTML reports for completed research jobs.

## Scope

In scope:

- Add derived progress metadata to research job detail responses.
- Show a dashboard timeline for Planner, Collector, Analyst, Critic, and Reporter.
- Show runtime, tool call count, and LLM call count on completed jobs.
- Add protected report export endpoints for Markdown and HTML.
- Add dashboard buttons for downloading Markdown and HTML reports.
- Update README, demo docs, and changelog.

Out of scope:

- WebSocket/SSE streaming.
- Persisting per-node execution events.
- Changing JSON/SQLite research job storage schema.
- Full Markdown-to-HTML compatibility beyond the safe report subset used by the dashboard.

## API Design

Job detail responses gain derived optional fields:

- `progress_stage`: one of `queued`, `planner`, `collector`, `analyst`, `critic`, `reporter`, `completed`, `failed`, `cancelled`.
- `progress_percent`: integer from 0 to 100.
- `progress_steps`: list of step objects with `id`, `label`, and `status`.
- `runtime_seconds`: integer when enough timestamps exist.
- `tool_call_count`: integer, derived from `result.tool_call_log` when available.
- `llm_call_count`: integer, derived from `result.llm_call_log` when available.

Progress is derived without changing stored jobs:

- `queued`: 0%, all steps pending.
- `running`: 20%, Planner active, because current MVP does not persist intra-workflow events.
- `succeeded`: 100%, all steps complete.
- `failed`: 100%, failed stage marker, step status failed.
- `cancelled`: 100%, cancelled marker, all steps pending/skipped.

Report export endpoints:

- `GET /research/jobs/{job_id}/report.md`
- `GET /research/jobs/{job_id}/report.html`

Both endpoints use the same API-key dependency as other job routes. They return 404 for unknown jobs, 409 when the job has no completed report, and safe report content only.

## Dashboard Design

The dashboard keeps the current static no-build approach. It adds:

- A timeline block in the Overview tab.
- New metric cards for `Runtime`, `Tools`, and `LLM Calls` in the selected job overview.
- Report tab actions for `Download Markdown` and `Download HTML`.
- Disabled download buttons when the selected job has no report.

The timeline uses the existing dark visual language: translucent cards, teal active state, green completed state, red failed state, muted pending state.

## Error Handling

- Report download buttons are disabled unless `result.report_markdown` exists.
- Export endpoint returns `409 {"detail":"Research job report is not available."}` for queued, running, failed, or cancelled jobs without a report.
- Export endpoints remain protected when `INSIGHT_GRAPH_API_KEY` is configured.
- Dashboard download actions use `fetch` with bearer auth and create an object URL, so API-key-protected exports work without exposing keys in URLs.

## Testing

Add tests for:

- Queued/running/succeeded/failed/cancelled progress metadata.
- Markdown report export success.
- HTML report export success and HTML escaping.
- Report export 409 before success.
- Report export auth protection.
- Dashboard HTML contains timeline and download controls.

Verification:

- `python -m pytest tests/test_api.py -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
