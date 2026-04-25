# Relevance Filtering Design

## Context

InsightGraph now has a first-stage Executor that runs planned tools, records tool calls, deduplicates evidence, and keeps default CLI behavior offline. It also has an opt-in `web_search -> pre_fetch -> fetch_url` flow that can use mock or DuckDuckGo providers.

The wenyi reference architecture filters pre-fetched evidence before storing it in the global evidence pool. The next increment adds that filtering point without introducing real LLM providers, API keys, or live network dependencies.

## Goals

- Add a relevance judge abstraction for evidence filtering.
- Add deterministic offline relevance filtering as the only supported judge in this phase.
- Integrate optional filtering into Executor after deduplication and before assigning `evidence_pool` / `global_evidence_pool`.
- Keep default behavior unchanged unless relevance filtering is explicitly enabled.
- Track how much evidence was filtered at tool-call level.
- Keep all tests offline and deterministic.

## Non-Goals

- No Qwen/OpenAI/real LLM relevance judge in this phase.
- No prompt design or API-key configuration.
- No async or batched relevance evaluation.
- No separate `relevance_log` state field.
- No change to Reporter citation logic.
- No change to default CLI behavior.

## State Model

Add `filtered_count: int = 0` to `ToolCallRecord`.

This keeps relevance filtering observability near the tool execution record without adding another top-level state collection.

## Relevance Module

Add `src/insight_graph/agents/relevance.py`.

Core units:

- `EvidenceRelevanceDecision`
  - `evidence_id: str`
  - `relevant: bool`
  - `reason: str`
- `RelevanceJudge` protocol
  - `judge(query: str, subtask: Subtask, evidence: Evidence) -> EvidenceRelevanceDecision`
- `DeterministicRelevanceJudge`
  - Returns not relevant if `evidence.verified is False`.
  - Returns not relevant if title, source URL, or snippet is empty after stripping whitespace.
  - Returns relevant otherwise.
- `is_relevance_filter_enabled() -> bool`
  - Reads `INSIGHT_GRAPH_RELEVANCE_FILTER`.
  - Truthy values: `"1"`, `"true"`, `"yes"` after lowercase normalization.
- `get_relevance_judge(name: str | None = None) -> RelevanceJudge`
  - Supports only `deterministic` in this phase.
  - Reads `INSIGHT_GRAPH_RELEVANCE_JUDGE`, default `deterministic`.
  - Unknown judge names raise `ValueError`.
- `filter_relevant_evidence(query, subtask, evidence, judge=None) -> tuple[list[Evidence], int]`
  - Applies judge to evidence in order.
  - Returns kept evidence and filtered count.

## Executor Integration

Executor currently performs:

```text
tool results -> collect -> deduplicate -> evidence_pool/global_evidence_pool
```

With filtering enabled it should perform:

```text
tool results -> collect -> deduplicate -> relevance filter -> evidence_pool/global_evidence_pool
```

Rules:

- Filtering is disabled unless `INSIGHT_GRAPH_RELEVANCE_FILTER` is truthy.
- When disabled, Executor behavior and `filtered_count` values remain unchanged at `0`.
- When enabled, filtering runs after deduplication.
- Filtering should be applied per subtask/tool result group before global assignment so each tool call can record its own `filtered_count`.
- Executor still deduplicates final kept evidence by `(id, source_url)`.
- Tool failures remain handled as before.

## Testing Strategy

- State tests verify `ToolCallRecord.filtered_count` default is `0`.
- Relevance tests verify deterministic judge decisions:
  - verified evidence with title/source URL/snippet is relevant;
  - unverified evidence is not relevant;
  - whitespace-only title, source URL, or snippet is not relevant;
  - unknown judge names raise `ValueError`;
  - filter env parsing only enables truthy values.
- Executor tests verify:
  - default filtering disabled preserves current behavior;
  - filtering enabled removes unverified evidence;
  - `filtered_count` records dropped evidence;
  - all filtering tests use fake registry output and do not access live network.
- Full graph and CLI tests still run with default filtering disabled.

## README Update

Document:

- Relevance filtering is opt-in via `INSIGHT_GRAPH_RELEVANCE_FILTER=1`.
- Current judge is deterministic/offline.
- Real LLM relevance filtering is future work.
- Default CLI behavior remains unchanged.

## Acceptance Criteria

- Default test suite output remains stable with filtering disabled.
- `ToolCallRecord.filtered_count` defaults to `0`.
- `INSIGHT_GRAPH_RELEVANCE_FILTER=1` enables deterministic filtering in Executor.
- Unverified or empty evidence is filtered when enabled.
- Tool call logs record filtered evidence counts.
- Full test suite passes without live network access.
- Ruff passes.
- Default CLI smoke test still produces a report without setting relevance env vars.

## Future Work

- Add Qwen/OpenAI relevance judge providers.
- Add prompt-based relevance decisions with structured JSON output.
- Add batched relevance evaluation for multiple evidence items.
- Add a dedicated relevance decision log if tool-call-level counts become insufficient.
