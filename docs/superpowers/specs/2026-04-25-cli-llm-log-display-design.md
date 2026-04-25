# CLI LLM Log Display Design

## Goal

Add an opt-in CLI flag that makes the existing in-memory `GraphState.llm_call_log` visible to command-line users after a research run, without changing default output or exposing prompts, completions, API keys, request bodies, headers, or raw exception payloads.

## Non-Goals

- Do not add JSON output in this iteration.
- Do not persist LLM call logs to disk or a database.
- Do not add token usage, cost tracking, trace IDs, or external telemetry.
- Do not change live-LLM defaults or deterministic offline behavior.

## User Experience

Default CLI behavior remains unchanged:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

To display LLM call metadata, users opt in explicitly:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --show-llm-log
```

When enabled and records exist, the CLI prints the Markdown report first, then appends:

```markdown
## LLM Call Log

| Stage | Provider | Model | Success | Duration ms | Error |
| --- | --- | --- | --- | ---: | --- |
| relevance | openai_compatible | gpt-4o-mini | true | 231 |  |
| analyst | llm | gpt-4o-mini | true | 812 |  |
| reporter | llm | gpt-4o-mini | false | 404 | ReporterFallbackError: LLM call failed. |
```

When enabled and no records exist, the CLI appends:

```markdown
## LLM Call Log

No LLM calls were recorded.
```

## Architecture

Add a `show_llm_log: bool` Typer option to the existing `research` command in `src/insight_graph/cli.py`.

Keep formatting local to the CLI module because this is presentation-only behavior. Add a small helper such as `_format_llm_call_log(records: list[LLMCallRecord]) -> str` that returns the Markdown block for the log section.

The command flow remains:

1. Configure output encoding through the existing callback.
2. Apply the selected runtime preset.
3. Run `run_research(query)`.
4. Print `state.report_markdown` as before.
5. If `show_llm_log` is true, append the formatted LLM log section.

## Safety Rules

The display helper may only read fields already present on `LLMCallRecord`:

- `stage`
- `provider`
- `model`
- `success`
- `duration_ms`
- `error`

It must not inspect prompt messages, completions, raw responses, environment variables, request bodies, headers, or exception objects.

The current observability helper stores generic failure summaries such as `RuntimeError: LLM call failed.`. The CLI should preserve that safety boundary and never reconstruct or enrich errors from raw exceptions.

Markdown table cell values should be normalized enough to avoid malformed output if a model or error string contains pipes or newlines. Replace `|` with `\|` and collapse line breaks to spaces.

## Testing

Add CLI tests with fake `run_research` functions so no external network or real LLM calls occur.

Test cases:

- Default `research` output does not include `## LLM Call Log`.
- `--show-llm-log` appends a Markdown table when `GraphState.llm_call_log` has records.
- `--show-llm-log` appends `No LLM calls were recorded.` when the log is empty.
- The displayed table includes stage, provider, model, success, duration, and sanitized error metadata.
- The displayed output does not include fake prompt, response, API key, request body, or header strings supplied elsewhere in the fake state/test setup.

Run at minimum:

```bash
python -m pytest tests/test_cli.py -q
python -m ruff check src/insight_graph/cli.py tests/test_cli.py
```

Final verification should run the full suite and lint:

```bash
python -m pytest -v
python -m ruff check .
```

## Rollout

This is an additive, opt-in CLI display feature. It does not alter default report output, existing presets, graph execution, or state models.
