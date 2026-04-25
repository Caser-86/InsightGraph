# Live LLM Preset Design

## Goal

Add a CLI preset that turns InsightGraph's existing opt-in live capabilities into one explicit command-line switch. The default CLI must remain deterministic and offline.

## User Experience

Default offline behavior stays unchanged:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

Live LLM mode becomes explicit:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm
```

The preset does not accept API keys on the command line. LLM credentials and endpoint settings continue to come from the existing environment variables:

- `INSIGHT_GRAPH_LLM_API_KEY` or `OPENAI_API_KEY`
- `INSIGHT_GRAPH_LLM_BASE_URL` or `OPENAI_BASE_URL`
- `INSIGHT_GRAPH_LLM_MODEL`

## Preset Behavior

`--preset live-llm` applies these runtime defaults for the research command:

- `INSIGHT_GRAPH_USE_WEB_SEARCH=1`
- `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo`
- `INSIGHT_GRAPH_RELEVANCE_FILTER=1`
- `INSIGHT_GRAPH_RELEVANCE_JUDGE=openai_compatible`
- `INSIGHT_GRAPH_ANALYST_PROVIDER=llm`
- `INSIGHT_GRAPH_REPORTER_PROVIDER=llm`

The preset should not permanently modify the user's environment. It should apply only during the current CLI invocation.

Existing explicitly configured environment values should win over preset defaults. For example, if a user runs with `INSIGHT_GRAPH_SEARCH_PROVIDER=mock`, the preset should not override that value. This keeps the preset useful as a convenience layer while preserving advanced control.

## CLI Contract

The research command accepts an optional preset argument:

```text
--preset [offline|live-llm]
```

Behavior:

- omitted or `offline`: use current behavior without setting live env defaults
- `live-llm`: apply the runtime defaults listed above
- unknown preset: Typer should reject the value before running the workflow

The implementation should prefer a small helper function that receives a preset name and applies missing environment values. Keeping this separate from the command body makes the behavior easy to test without invoking network or LLM calls.

## Error Handling

The preset should not preflight API keys or network access. Existing components already handle missing keys, provider errors, invalid JSON, and fallback paths. Avoid adding a second layer of partial validation that could diverge from component behavior.

Unknown preset values should fail fast through CLI argument validation.

## Testing

Tests must not access the network or real LLM providers.

Add unit coverage for:

- default research command still runs offline and does not require LLM env
- `live-llm` preset sets missing runtime env defaults before calling `run_research`
- explicit existing env values are not overwritten by the preset
- unknown preset values are rejected by the CLI

Use monkeypatching and a fake `run_research` result where needed. Do not call DuckDuckGo or external LLM APIs in tests.

## Documentation

Update `README.md` with a short `live-llm` preset section showing:

- default offline command
- live preset command
- required LLM environment variables
- note that the preset enables DuckDuckGo search, LLM relevance, LLM Analyst, and LLM Reporter

## Non-Goals

- No config file support in this increment
- No command-line API key argument
- No Responses API adapter changes
- No FastAPI or frontend work
- No persistent environment mutation
