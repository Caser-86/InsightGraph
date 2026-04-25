# Web Search Mock Fallback Design

## Goal

Prevent `--preset live-llm` runs from producing empty reports when the live web search provider returns no evidence or fails. If `web_search` cannot produce evidence, InsightGraph should fall back to deterministic `mock_search` evidence and make the fallback visible in `tool_call_log`.

## Non-Goals

- Do not hide live search failures.
- Do not change default offline behavior.
- Do not add a new search provider.
- Do not retry DuckDuckGo requests.
- Do not make fallback evidence look like live web evidence.
- Do not apply fallback to `mock_search` itself.

## Current Behavior

`DuckDuckGoSearchProvider.search()` returns an empty list on exceptions. `web_search()` then returns an empty evidence list. `execute_subtasks()` records the tool call as successful with `evidence_count=0`, leaving downstream analyst/reporter stages with no evidence.

Observed live smoke outcome:

- `tool_call_log` contains `web_search` records with `success=true` and `evidence_count=0`.
- Analyst LLM calls still run, but parse/validation fails because there is no evidence to cite.
- Final report has no key findings or references.
- Token observability works, but the live workflow is not useful.

## Design

Add fallback handling in `src/insight_graph/agents/executor.py`, not inside `DuckDuckGoSearchProvider`.

Executor owns `ToolCallRecord`, so this layer can truthfully record both events:

1. The original live `web_search` produced no usable evidence or failed.
2. `mock_search` was used as deterministic fallback evidence.

### Empty Result Fallback

When a subtask requests `web_search` and `registry.run("web_search", ...)` returns an empty list:

- Append a `ToolCallRecord` for `web_search`:
  - `tool_name="web_search"`
  - `success=False`
  - `evidence_count=0`
  - `filtered_count=0`
  - `error="web_search returned no evidence; falling back to mock_search"`
- Run `registry.run("mock_search", ...)`.
- Process mock results through the same dedupe and optional relevance filtering path used for normal tool results.
- Append a `ToolCallRecord` for `mock_search`:
  - `tool_name="mock_search"`
  - `success=True` when fallback succeeds
  - `evidence_count=<raw mock result count>`
  - `filtered_count=<filtered count after relevance filtering>`
  - `error="fallback for web_search"`

### Exception Fallback

When a subtask requests `web_search` and `registry.run("web_search", ...)` raises:

- Append a failed `web_search` record with the current sanitized/plain tool error behavior.
- Run the same `mock_search` fallback path.
- If fallback succeeds, append the same successful fallback record described above.
- If fallback also fails, append a failed `mock_search` record:
  - `tool_name="mock_search"`
  - `success=False`
  - `evidence_count=0`
  - `filtered_count=0`
  - `error="fallback for web_search failed: <exception text>"`

### Scope Guard

Only `web_search` gets this fallback. Other tools keep existing behavior: exceptions create a failed record and execution continues; empty result lists are recorded as successful empty results.

This avoids fallback loops and keeps behavior explicit.

## Data Flow

For `--preset live-llm`:

1. Preset sets `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo` and planner suggests `web_search`.
2. Executor runs `web_search`.
3. If `web_search` returns evidence, behavior is unchanged.
4. If `web_search` returns no evidence or raises, executor records the failed live attempt and runs `mock_search`.
5. Mock evidence flows through dedupe, relevance filtering, analyst, critic, and reporter as usual.
6. The final report can be complete, and `tool_call_log` reveals fallback usage.

## CLI And JSON Output

No CLI flag changes are required.

`--output-json` already includes `tool_call_log`, so fallback records are visible there.

`--show-llm-log` is unaffected because this is tool observability, not LLM observability.

## Safety And Honesty

Fallback evidence must retain existing mock evidence source URLs and metadata. Do not relabel fallback evidence as DuckDuckGo evidence.

The failed `web_search` record must remain in `tool_call_log` so users can see that live search did not provide evidence.

## Testing

Add tests with fake registries only. Do not access the network.

Coverage:

- `web_search` empty result triggers a failed `web_search` record and successful `mock_search` fallback record.
- fallback mock evidence populates `evidence_pool` and `global_evidence_pool`.
- relevance filtering still runs on fallback evidence when enabled.
- `web_search` exception triggers fallback and records both the original failure and fallback success.
- fallback failure records a failed `mock_search` record and does not crash the executor.
- empty results from non-`web_search` tools keep existing successful-empty behavior.
- README documents that live preset may fall back to deterministic mock evidence when live search is unavailable or empty.

Run at minimum:

```bash
python -m pytest tests/test_executor.py tests/test_cli.py -q
python -m ruff check src/insight_graph/agents/executor.py tests/test_executor.py README.md
```

Final verification:

```bash
python -m pytest -v
python -m ruff check .
```

Live smoke after implementation:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --output-json
```

Expected live smoke behavior when DuckDuckGo returns no evidence:

- `tool_call_log` contains failed `web_search` records.
- `tool_call_log` contains successful `mock_search` fallback records.
- `evidence_pool` is still omitted from JSON output.
- report contains key findings and references from fallback evidence.
- `llm_call_log` may include token fields if LLM stages are attempted and provider usage is returned.

## Rollout

This is a live-mode resilience improvement. Offline deterministic behavior remains unchanged. Live users get a complete demo/report path when the live search provider is unavailable, while the fallback remains visible in logs.
