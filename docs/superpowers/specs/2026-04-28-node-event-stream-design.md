# Node Event Stream Design

## Goal

Make the dashboard stream resemble the reference project's real-time agent execution trace by emitting stage, tool, LLM, and report events while jobs run.

## Scope

In scope:

- Add `run_research_with_events(user_request, emit_event)`.
- Emit safe lifecycle events for Planner, Collector, Analyst, Critic, retry, and Reporter stages.
- Emit safe `tool_call` and `llm_call` events when new records appear in `GraphState`.
- Add an in-memory per-process job event broker with bounded replay.
- Extend `WS /research/jobs/{job_id}/stream` to send snapshots plus cached/live events.
- Add a Live Events area in the static dashboard.

Out of scope:

- Persisting event logs to JSON/SQLite/PostgreSQL.
- Cross-process event fanout for SQLite multi-worker deployments.
- Streaming prompts, completions, raw LLM responses, request bodies, headers, API keys, or provider payloads.
- Changing public job storage schema.

## Event Types

Events are JSON-safe objects and may include an internal monotonic `sequence` number:

```json
{"type":"stage_started","stage":"planner"}
{"type":"stage_finished","stage":"collector"}
{"type":"tool_call","record":{"tool_name":"mock_search","success":true}}
{"type":"llm_call","record":{"stage":"analyst","model":"...","success":true}}
{"type":"report_ready","job_id":"..."}
{"type":"job_snapshot","job":{}}
```

## Graph Runner

`run_research_with_events()` follows the same logical order as `run_research()`:

Planner → Collector → Analyst → Critic → optional retry loop → Reporter.

It does not use LangGraph's compiled invoke path internally because the current graph has a simple fixed topology and direct node calls make event boundaries explicit and testable. Existing `run_research()` remains unchanged.

## Broker

The API module owns a lightweight in-memory broker:

- Stores recent events per `job_id` up to a bounded limit.
- Lets WebSocket clients replay cached events after the initial snapshot.
- Publishes live events to connected clients through thread-safe queues.
- Drops events on process restart.

## Dashboard

Dashboard adds a `Live Events` tab/section:

- Shows stage events with compact status chips.
- Shows tool and LLM calls with safe metadata only.
- Updates live from WebSocket events.
- Keeps polling fallback for snapshots when stream is unavailable.

## Testing

Add tests for:

- `run_research_with_events()` emits stage events in order and produces the same result shape as `run_research()`.
- WebSocket stream replays cached job events after the initial snapshot.
- Worker execution publishes stage events for a completed job.
- Dashboard HTML contains Live Events markers.

Verification:

- `python -m pytest tests/test_graph.py tests/test_api.py -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
