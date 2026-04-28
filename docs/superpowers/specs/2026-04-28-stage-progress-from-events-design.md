# Stage Progress From Events Design

## Goal

Use the in-process execution event cache to make running job progress reflect the actual current graph stage instead of always showing `planner`.

## Scope

In scope:

- Derive `progress_stage`, `progress_percent`, and `progress_steps` for running jobs from cached `stage_started` and `stage_finished` events.
- Keep succeeded, failed, cancelled, and queued behavior compatible with existing responses.
- Make WebSocket `job_snapshot` events include event-derived progress when stage events are present.
- Keep the dashboard timeline unchanged where possible because it already consumes `progress_steps`.

Out of scope:

- Persisting stage progress to JSON or SQLite job stores.
- Changing public job storage schemas.
- Cross-process stage progress fanout.
- Frontend-only stage derivation.

## Event-Derived Progress

For `running` jobs, REST and WebSocket snapshots inspect cached events for the same `job_id`.

Stage mapping:

- `planner`: 20%
- `collector`: 40%
- `analyst`: 60%
- `critic`: 80%
- `reporter`: 95%

Rules:

- No cached stage events: preserve existing fallback, `planner` active and 20%.
- A `stage_started` event makes that stage active.
- A `stage_finished` event marks that stage completed.
- Stages before the current active stage are completed.
- Stages after the current active stage are pending.
- If all known stages are finished while the job is still marked running, reporter remains active at 95% until the job transitions to `succeeded`.
- `succeeded` remains 100% with all steps completed.
- `failed` uses the latest cached active stage as failed when available; otherwise it keeps the existing planner-failed fallback.
- `cancelled` remains 100% with all steps skipped.

## API Behavior

No response fields are added. Existing fields become more precise:

```json
{
  "progress_stage": "collector",
  "progress_percent": 40,
  "progress_steps": [
    {"id":"planner","label":"Planner","status":"completed"},
    {"id":"collector","label":"Collector","status":"active"},
    {"id":"analyst","label":"Analyst","status":"pending"},
    {"id":"critic","label":"Critic","status":"pending"},
    {"id":"reporter","label":"Reporter","status":"pending"}
  ]
}
```

## Dashboard Behavior

The dashboard timeline automatically reflects the derived progress because it already renders `progress_steps`. The Live Events tab remains the raw trace view.

## Testing

Add tests for:

- Running job with cached `collector` events returns collector active progress.
- WebSocket snapshot includes event-derived progress.
- Failed job with cached active stage marks that stage failed.
- Existing queued/running/succeeded/cancelled behavior remains compatible when no events exist.

Verification:

- `python -m pytest tests/test_api.py::test_get_research_job_derives_running_progress_from_stage_events tests/test_api.py::test_research_job_stream_snapshot_uses_stage_event_progress tests/test_api.py::test_get_research_job_derives_failed_stage_from_stage_events -v`
- `python -m pytest tests/test_api.py tests/test_graph.py -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
