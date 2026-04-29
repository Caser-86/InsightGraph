# run_with_llm_log Parity Design

## Goal

Make `scripts/run_with_llm_log.py` behave like the reference diagnostic runner: one command runs research, captures full LLM input/output/token traces, and prints token/call summary statistics.

## Reference Alignment

The reference README describes `scripts/run_with_llm_log.py` as a run entry point that records every LLM call into `llm_logs/` and reports call count plus input/output/total token usage. InsightGraph already has safe metadata logging and an opt-in JSONL full trace writer. This phase connects them.

## Scope

- `scripts/run_with_llm_log.py` enables full trace by default because it is an explicit diagnostic entry point.
- Each run writes two files in `llm_logs/` or `--log-dir`:
  - `<timestamp-slug>.jsonl`: full LLM call trace with messages/output/token usage.
  - `<timestamp-slug>.json`: safe run metadata plus trace summary.
- Add `--safe-log-only` to preserve the old safe metadata-only behavior.
- Print reference-style summary lines to stdout.
- Ordinary CLI/API behavior remains unchanged.

## Design

`build_log_path()` continues to create the metadata JSON path. A sibling helper derives the trace JSONL path from that JSON path by replacing `.json` with `.jsonl`.

Before running the workflow, the script sets `INSIGHT_GRAPH_LLM_TRACE_PATH` to the trace path unless `--safe-log-only` is passed. After workflow completion, the script reads the JSONL trace and builds:

- `call_count`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `by_stage`
- `by_model`

The metadata JSON includes `llm_trace_path` and `llm_trace_summary` when full tracing is enabled. Stdout appends summary lines after the report and log path.

## Testing

- Full trace mode sets `INSIGHT_GRAPH_LLM_TRACE_PATH` before workflow execution.
- Existing safe metadata remains when `--safe-log-only` is passed.
- JSONL summary aggregates token usage and call counts.
- Stdout includes reference-style summary lines.
- Tests use fake workflow functions and temporary directories only.

## Non-Goals

- No external LLM calls in tests.
- No dashboard trace viewer.
- No trace redaction in full diagnostic mode.
