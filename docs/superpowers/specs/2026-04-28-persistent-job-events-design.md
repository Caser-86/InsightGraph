# Persistent Job Events Design

## Goal

Persist safe job execution events so completed or restarted jobs can still replay their execution trace and derive progress even when the in-memory event cache is empty.

## Scope

In scope:

- Add an `events` field to retained `ResearchJob` records.
- Persist bounded safe events in both JSON and SQLite job stores.
- Replay persisted events over `WS /research/jobs/{job_id}/stream` when memory cache is empty.
- Derive progress from persisted events when memory cache is empty.
- Include events in job detail responses, but not job list or summary responses.

Out of scope:

- A separate event query endpoint.
- Event pagination.
- Cross-process live pub/sub.
- Persisting prompts, completions, headers, API keys, raw provider payloads, or request bodies.

## Data Model

`ResearchJob` gets:

```python
events: list[dict[str, Any]] = field(default_factory=list)
```

Events use the same safe payloads already emitted by the in-memory broker and retain their `sequence` field. The retained list is bounded by `_RESEARCH_JOB_EVENT_LIMIT`.

## Storage

JSON store:

- `serialize_research_job()` writes `events`.
- `load_research_jobs()` accepts old jobs without `events` and defaults them to `[]`.

SQLite backend:

- Add nullable `events_json TEXT` to `research_jobs`.
- `initialize()` migrates existing databases missing `events_json`.
- `job_to_row()` writes JSON events.
- `job_from_row()` parses events or defaults to `[]`.

## API Behavior

- `_publish_research_job_event()` writes to the in-memory broker and persists the same event to the job record.
- `_cached_research_job_events(job_id)` returns in-memory events first, then persisted events.
- `_stage_progress_from_events()` uses that combined read path, so REST snapshots can derive progress after process-local cache loss.
- `GET /research/jobs/{job_id}` includes `events` for detail views.
- List and summary responses omit events.

## Failure Handling

Event persistence is best-effort. If a store write fails while appending an event, live streaming still continues from memory and the job itself can still complete. Terminal job state remains the source of truth.

## Testing

Add tests for:

- JSON store saves and reloads job events.
- JSON store loads old jobs without `events`.
- SQLite schema includes and migrates `events_json`.
- `_publish_research_job_event()` persists event history into job detail.
- WebSocket replay works from persisted events after clearing memory cache.
- Progress derives from persisted events after clearing memory cache.

Verification:

- `python -m pytest tests/test_research_jobs_store.py tests/test_research_jobs_sqlite_backend.py tests/test_api.py -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
