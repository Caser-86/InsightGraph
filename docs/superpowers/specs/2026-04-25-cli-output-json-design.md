# CLI Output JSON Design

## Goal

Add an opt-in `--output-json` mode to the `research` CLI command so scripts can consume a safe, structured summary of a research run, including `llm_call_log`, without changing the default Markdown output.

## Non-Goals

- Do not output the complete `GraphState` in this iteration.
- Do not include `evidence_pool` or `global_evidence_pool` because those can contain fetched snippets and make stdout large.
- Do not persist JSON to files.
- Do not add streaming, JSON Lines, token usage, cost tracking, or trace IDs.
- Do not change live-LLM preset behavior.

## User Experience

Default CLI behavior remains Markdown:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

Structured output is explicit:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

The JSON output is pretty-printed to stdout and contains this top-level shape:

```json
{
  "user_request": "Compare Cursor, OpenCode, and GitHub Copilot",
  "report_markdown": "# InsightGraph Research Report\n...",
  "findings": [],
  "critique": null,
  "tool_call_log": [],
  "llm_call_log": [],
  "iterations": 0
}
```

If users pass both `--output-json` and `--show-llm-log`, JSON mode wins. The CLI returns JSON only and does not append the Markdown `## LLM Call Log` section.

## Architecture

Keep the feature in `src/insight_graph/cli.py` because it is CLI presentation behavior. Add a small serializer helper, for example `_build_research_json_payload(state: GraphState) -> dict[str, object]`, that explicitly selects fields for the summary JSON.

The `research` command flow becomes:

1. Configure output encoding through the existing callback.
2. Apply the selected runtime preset.
3. Run `run_research(query)`.
4. If `output_json` is true, print JSON and return.
5. Otherwise, print the Markdown report as today.
6. If `show_llm_log` is true in Markdown mode, append the Markdown LLM log section.

Use Pydantic `model_dump(mode="json")` for nested model lists and optional models to avoid manual object conversion:

- `finding.model_dump(mode="json")`
- `state.critique.model_dump(mode="json")` when present
- `record.model_dump(mode="json")` for tool and LLM logs

Use `json.dumps(payload, indent=2, ensure_ascii=False)` so non-ASCII report text remains readable and stable on UTF-8 output streams.

## JSON Fields

The initial JSON payload includes exactly these fields:

- `user_request`: original request string.
- `report_markdown`: report Markdown string or empty string when absent.
- `findings`: list of finding objects.
- `critique`: critique object or `null`.
- `tool_call_log`: list of tool call record objects.
- `llm_call_log`: list of LLM call record objects.
- `iterations`: integer retry/iteration count.

The payload intentionally excludes:

- `subtasks`
- `evidence_pool`
- `global_evidence_pool`

These can be added later behind a separate explicit option if evidence export becomes necessary.

## Safety Rules

The JSON serializer must only read fields already present in `GraphState` and its Pydantic child models. It must not inspect prompts, completions, raw responses, environment variables, API keys, authorization headers, request bodies, or exception objects.

`llm_call_log` entries are safe to expose because the existing observability layer stores metadata only: stage, provider, model, success, duration, and sanitized generic error summaries.

Tests should include fake prompt, response, API key, request body, header, and evidence snippet strings in omitted fields or surrounding test setup to prove `--output-json` does not leak them.

## Error Handling

Do not make `--output-json` mutually exclusive with `--show-llm-log` at the Typer validation layer. JSON mode should take precedence because this avoids unnecessary CLI friction and keeps automated scripts deterministic.

If `run_research()` raises, current CLI behavior should remain unchanged; this feature does not add new error wrappers.

## Testing

Add CLI tests with fake `run_research` functions so no external network or real LLM calls occur.

Test cases:

- Default `research` output remains Markdown and is not JSON.
- `--output-json` emits parseable JSON.
- JSON contains `user_request`, `report_markdown`, `findings`, `critique`, `tool_call_log`, `llm_call_log`, and `iterations`.
- JSON omits `subtasks`, `evidence_pool`, and `global_evidence_pool`.
- JSON does not include fake prompt, response, API key, request body, authorization header, or evidence snippet strings.
- Passing both `--output-json` and `--show-llm-log` outputs JSON only and does not append `## LLM Call Log`.

Run at minimum:

```bash
python -m pytest tests/test_cli.py -q
python -m ruff check src/insight_graph/cli.py tests/test_cli.py
```

Final verification should run:

```bash
python -m pytest -v
python -m ruff check .
```

## Rollout

This is an additive, opt-in CLI output mode. It does not alter default Markdown output, existing presets, graph execution, or state models.
