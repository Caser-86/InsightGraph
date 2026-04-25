# Executor Web Search Design

## Context

InsightGraph currently has a simple `Collector` node that loops over planned subtasks and runs each subtask's `suggested_tools`. This is enough for the MVP mock flow, but it does not yet match the wenyi reference architecture's Executor shape: tool-call logging, shared evidence pool, explicit web-search path, and future multi-round tool execution.

The previous increment added a configurable `web_search` tool with mock and DuckDuckGo providers. This increment wires that capability into the research flow behind an explicit opt-in switch while preserving the default offline CLI behavior.

## Goals

- Add a first-stage `Executor` agent that replaces the current direct Collector implementation internally.
- Preserve `collect_evidence(state)` as a compatibility wrapper for the graph and tests.
- Add `global_evidence_pool` to state for wenyi-style cross-subtask evidence sharing.
- Add `tool_call_log` to state for observable tool execution records.
- Add an explicit planner switch: `INSIGHT_GRAPH_USE_WEB_SEARCH=1` makes the collect subtask suggest `web_search` instead of `mock_search`.
- Keep default Planner and CLI behavior offline and deterministic.
- Ensure tool failures are logged and do not crash the whole graph.
- Deduplicate evidence before storing it in state.

## Non-Goals

- No LLM relevance filtering in this phase.
- No real multi-round LLM tool-decision loop in this phase.
- No conversation compression.
- No no-new-evidence convergence detection.
- No PDF, Playwright, Trafilatura, or RAG changes.
- No default live-network behavior.

## State Model

Add `ToolCallRecord` to `src/insight_graph/state.py`:

- `subtask_id: str`
- `tool_name: str`
- `query: str`
- `evidence_count: int = 0`
- `success: bool = True`
- `error: str | None = None`

Add fields to `GraphState`:

- `global_evidence_pool: list[Evidence] = Field(default_factory=list)`
- `tool_call_log: list[ToolCallRecord] = Field(default_factory=list)`

`evidence_pool` remains the current per-run evidence collection consumed by Analyst, Critic, and Reporter. In this phase `global_evidence_pool` mirrors the deduplicated evidence accumulated by Executor so future subtasks and future memory/RAG work have a stable extension point.

## Planner Behavior

`plan_research(state)` keeps the same four subtasks and descriptions.

The collect subtask chooses tools as follows:

- Default: `suggested_tools=["mock_search"]`
- If `INSIGHT_GRAPH_USE_WEB_SEARCH=1`: `suggested_tools=["web_search"]`

Accepted truthy values are only `"1"`, `"true"`, and `"yes"` after lowercase normalization. Any other value keeps default mock behavior.

`INSIGHT_GRAPH_SEARCH_PROVIDER` continues to be interpreted by the `web_search` tool itself. This keeps concerns separate:

- `INSIGHT_GRAPH_USE_WEB_SEARCH` chooses whether the research flow calls `web_search`.
- `INSIGHT_GRAPH_SEARCH_PROVIDER` chooses which search provider `web_search` uses.

## Executor Behavior

Add `src/insight_graph/agents/executor.py` with `execute_subtasks(state: GraphState) -> GraphState`.

Executor rules:

- Instantiate `ToolRegistry` once per execution.
- Iterate over `state.subtasks` in order.
- Skip subtasks with no `suggested_tools`.
- For each suggested tool, call `registry.run(tool_name, state.user_request, subtask.id)`.
- On success, append a `ToolCallRecord` with `success=True` and `evidence_count=len(results)`.
- On exception, append a `ToolCallRecord` with `success=False`, `evidence_count=0`, and the exception message; continue to the next tool.
- Deduplicate evidence by stable key before assigning state fields.

Deduplication key:

```text
(evidence.id, evidence.source_url)
```

This preserves distinct evidence if either id or URL differs, while avoiding repeat records from repeated tool execution.

After execution:

- `state.evidence_pool` becomes the deduplicated evidence list from this Executor run.
- `state.global_evidence_pool` becomes the same deduplicated list for this phase.
- Existing `state.tool_call_log` entries are preserved and new entries are appended.

## Collector Compatibility

Keep `src/insight_graph/agents/collector.py` and its public function name:

```python
def collect_evidence(state: GraphState) -> GraphState:
    return execute_subtasks(state)
```

This avoids graph and test churn while introducing the Executor boundary.

## Error Handling

Unknown tools and tool runtime failures are contained at Executor level:

- The failing tool call is logged.
- The graph continues.
- If no evidence is collected, Critic should fail using the existing critique path.

This mirrors wenyi's resilience direction without introducing retry/replan strategy changes in this phase.

## Testing Strategy

- State tests verify `ToolCallRecord` defaults and new `GraphState` list defaults.
- Planner tests verify default `mock_search` and opt-in `web_search` behavior.
- Executor tests verify:
  - default mock evidence is collected;
  - `tool_call_log` records successful calls;
  - `global_evidence_pool` mirrors deduplicated evidence;
  - duplicate evidence is removed;
  - tool failures are logged and do not raise.
- Graph/CLI tests keep default offline behavior.
- Web-search opt-in tests monkeypatch registry/tool calls and must not access live network.

## README Update

Update the MVP notes to mention:

- Default CLI remains mock/offline.
- `INSIGHT_GRAPH_USE_WEB_SEARCH=1` switches the research flow to `web_search`.
- `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo` can then make `web_search` use DuckDuckGo.
- This is still a first-stage Executor and does not yet include LLM relevance filtering or multi-round agentic tool decisions.

## Acceptance Criteria

- Default `plan_research()` still suggests `mock_search`.
- With `INSIGHT_GRAPH_USE_WEB_SEARCH=1`, `plan_research()` suggests `web_search`.
- `collect_evidence()` delegates to Executor and still returns verified mock evidence by default.
- Executor records successful and failed tool calls in `tool_call_log`.
- Executor deduplicates evidence and fills `global_evidence_pool`.
- Full test suite passes without live network access.
- Ruff passes.
- Default CLI smoke test still produces a report without setting web-search env vars.

## Future Work

- Add a true multi-round Executor loop with `MAX_TOOL_ROUNDS`.
- Add LLM relevance filtering after pre-fetch.
- Add no-new-evidence convergence detection.
- Add conversation compression and budget controls.
- Add Qwen Search and GitHub-specific search providers.
