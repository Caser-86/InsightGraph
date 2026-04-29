# Full LLM Trace Design

## Goal

Align with the reference `llm_logger` design by supporting full LLM call logging for diagnostics: input messages, output text, token usage, duration, and stage metadata.

## Reference Alignment

The reference agent records every LLM call's input, output, and token usage under `llm_logs/` for post-run analysis. InsightGraph will add the same capability as an explicit diagnostic mode while preserving safe defaults.

## Scope

- Add a JSONL trace writer for LLM calls.
- Default trace directory: `llm_logs/`.
- Enable full tracing only when `INSIGHT_GRAPH_LLM_TRACE=1` or `INSIGHT_GRAPH_LLM_TRACE_PATH` is set.
- Include payloads by default when full tracing is explicitly enabled, matching the reference design.
- Keep normal CLI/API/tests from writing trace files unless explicitly enabled.
- Record stage, provider, model, messages, output text, token usage, success/error, duration, and timestamp.

## Design

Add `insight_graph.llm.trace_writer` with:

- `is_llm_trace_enabled()` for env gating.
- `resolve_llm_trace_path()` returning `INSIGHT_GRAPH_LLM_TRACE_PATH` or `llm_logs/llm-trace.jsonl`.
- `write_llm_trace_event(event)` appending one JSON object per line.

`build_full_trace_event()` remains the event builder. When full trace is enabled, Analyst and Reporter LLM paths will call it with `include_payload=True` and pass the result to the trace writer. Failed LLM calls will write an event with error metadata and no output text if no model output exists.

The initial implementation will wire Analyst and Reporter because those are the main generation stages. Relevance judge trace wiring can follow in a later phase if needed.

## Testing

- Trace disabled by default writes no file.
- Trace writer creates parent directories and appends JSONL.
- Reporter successful LLM calls write messages, output text, token usage, duration, and timestamp when enabled.
- Reporter failed LLM calls write error metadata when enabled.
- Tests use tmp paths and fake LLM clients only.

## Non-Goals

- No redaction in full payload mode; enabling it is explicit diagnostic behavior.
- No live LLM calls in tests.
- No dashboard trace viewer in this phase.
