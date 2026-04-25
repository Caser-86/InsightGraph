# LLM Reporter Design

## Goal

Add an opt-in OpenAI-compatible LLM Reporter that produces more professional Markdown reports while preserving deterministic/offline defaults and system-controlled citations.

The LLM Reporter should improve narrative quality, structure, and executive readability. It must not create new facts, invent sources, or control the final references list.

## Scope

In scope:

- Add `INSIGHT_GRAPH_REPORTER_PROVIDER=llm` as an opt-in Reporter provider.
- Keep `INSIGHT_GRAPH_REPORTER_PROVIDER` defaulting to `deterministic`.
- Reuse the existing shared `insight_graph.llm` OpenAI-compatible client layer.
- Let LLM Reporter generate the report body from `GraphState.user_request`, `GraphState.findings`, verified evidence, and optional critique.
- Validate the LLM report body before accepting it.
- Strip any LLM-provided `## References` section.
- Always append deterministic `## References` generated from verified evidence.
- Fall back to deterministic Reporter on expected LLM/config/output validation failures.
- Keep all tests offline with fake LLM clients.
- Update README route-map text that still describes LLM routing as future-only.

Out of scope:

- Domain-specific report templates.
- Streaming report generation.
- Long report chunking.
- Token budgets.
- Prompt/response persistence or tracing.
- Planner, Collector, Analyst, Critic, or Executor changes.
- Letting LLM create or rewrite final source URLs.

## Default Behavior

Default CLI behavior must not change.

- Without `INSIGHT_GRAPH_REPORTER_PROVIDER=llm`, `write_report()` uses the current deterministic Markdown report.
- Tests must not require API keys or network access.
- `INSIGHT_GRAPH_LLM_API_KEY`, `INSIGHT_GRAPH_LLM_BASE_URL`, and `INSIGHT_GRAPH_LLM_MODEL` remain inert for Reporter unless `INSIGHT_GRAPH_REPORTER_PROVIDER=llm` is set.
- Existing Analyst and Relevance LLM opt-ins remain independent.

## Configuration

Reporter provider selection:

| Variable | Meaning | Default |
|----------|---------|---------|
| `INSIGHT_GRAPH_REPORTER_PROVIDER` | `deterministic` or `llm` | `deterministic` |

LLM Reporter reuses the shared LLM config:

| Variable | Meaning | Default |
|----------|---------|---------|
| `INSIGHT_GRAPH_LLM_API_KEY` | OpenAI-compatible provider API key; fallback to `OPENAI_API_KEY` | `None` |
| `INSIGHT_GRAPH_LLM_BASE_URL` | OpenAI-compatible `/v1` endpoint; fallback to `OPENAI_BASE_URL` | `None` |
| `INSIGHT_GRAPH_LLM_MODEL` | OpenAI-compatible Reporter model | `gpt-4o-mini` |

Unknown reporter provider names should raise `ValueError` when resolved through `get_reporter_provider()`. The graph default remains deterministic because the default provider is `deterministic`.

## Architecture

### `src/insight_graph/agents/reporter.py`

Keep this feature local to `reporter.py` because Reporter is currently small and has one responsibility.

Responsibilities after the change:

- Keep deterministic report generation in `_write_report_deterministic(state)`.
- Add `get_reporter_provider(name: str | None = None) -> str`.
- Update `write_report(state, llm_client: ChatCompletionClient | None = None) -> GraphState`.
- Add `_write_report_with_llm(state, llm_client=None)`.
- Add `_build_reporter_messages(state, reference_numbers)`.
- Add `_validate_llm_report_body(markdown, allowed_reference_numbers)`.
- Add `_strip_references_section(markdown)`.
- Add `_build_references_section(verified_evidence, reference_numbers)`.

`write_report()` should:

- resolve provider;
- call deterministic Reporter if provider is `deterministic`;
- call LLM Reporter if provider is `llm`;
- fall back to deterministic Reporter only for expected `ValueError` failures from config, client call, or validation;
- not swallow unexpected programming errors outside the LLM client call boundary.

### Shared LLM Layer

Use existing `ChatCompletionClient`, `ChatMessage`, `resolve_llm_config`, and `get_llm_client`.

Reporter should not create a new LLM client abstraction.

## Data Flow

1. `Reporter` receives a `GraphState` after Critic.
2. It builds `verified_evidence` and deterministic `reference_numbers` from `state.evidence_pool`.
3. If provider is `deterministic`, it produces the current report unchanged.
4. If provider is `llm`:
   - ensure API key exists unless an injected fake client is provided;
   - build messages with user request, findings, critique, and verified evidence reference numbers;
   - call `complete_json()` on the LLM client;
   - parse a JSON object with `markdown` string;
   - strip any LLM-provided `## References` section;
   - validate required sections and citations;
   - append deterministic Critic Assessment if the accepted body does not include it and state has critique;
   - append deterministic References.
5. If any expected LLM/config/output failure occurs, deterministic Reporter output is used.

Expected LLM JSON shape:

```json
{
  "markdown": "# InsightGraph Research Report\n\n**Research Request:** ...\n\n## Key Findings\n\n... [1]"
}
```

The LLM is instructed not to include `## References`, but the system must still strip it if present.

## Prompt Requirements

The Reporter prompt should include:

- research request;
- accepted findings with titles, summaries, and reference numbers derived from their evidence IDs;
- verified evidence list with deterministic reference numbers, titles, URLs, source types, and snippets;
- optional Critic Assessment reason;
- instructions to return only JSON with a `markdown` string;
- instructions to cite only allowed reference numbers such as `[1]` or `[1] [2]`;
- instruction not to invent sources or add a references section.

The prompt should not include unverified evidence.

## Output Validation

An accepted LLM report body must satisfy all rules:

- It is a non-empty string from JSON field `markdown`.
- It contains `# InsightGraph Research Report`.
- It contains `## Key Findings`.
- It contains at least one legal citation.
- Every citation token matching `[number]` uses a number present in the deterministic reference number set.
- It does not rely on LLM-provided references because any `## References` section is stripped before final assembly.

Invalid output triggers deterministic fallback.

The final report should always end with deterministic references generated from verified evidence:

```markdown
## References

[1] Evidence title. https://example.com/source
```

If `state.critique` exists and the accepted LLM body does not contain `## Critic Assessment`, append deterministic Critic Assessment before References.

## Error Handling

Fallback to deterministic Reporter for expected failures:

- missing API key;
- LLM client/API error;
- empty content;
- invalid JSON;
- JSON schema missing `markdown`;
- missing required sections;
- illegal citation number;
- no legal citation;
- no verified evidence references available.

Do not broadly catch all exceptions around prompt construction or validation implementation bugs. Wrap only `llm_client.complete_json(...)` exceptions into `ValueError` so API/client failures use deterministic fallback while programming errors remain visible.

## Tests

Add or update tests without live network access.

### Reporter Provider Tests

- `get_reporter_provider()` defaults to `deterministic` when env is clear.
- Unknown provider raises `ValueError`.

### Default Behavior Tests

- Existing deterministic Reporter tests still pass.
- Default graph and CLI behavior remains deterministic/offline when Reporter/LLM env vars are absent.
- Default-path tests clear `INSIGHT_GRAPH_REPORTER_PROVIDER`, `INSIGHT_GRAPH_LLM_API_KEY`, and `OPENAI_API_KEY` to avoid accidental live calls.

### LLM Reporter Tests

- Valid fake LLM Markdown is accepted and appears in final report.
- Final report appends deterministic `## References`.
- LLM-provided fake `## References` content is stripped.
- Missing API key falls back to deterministic report.
- LLM API error falls back to deterministic report.
- Empty content falls back to deterministic report.
- Invalid JSON falls back to deterministic report.
- Missing `markdown` field falls back to deterministic report.
- Missing required heading falls back to deterministic report.
- Illegal citation such as `[99]` falls back to deterministic report.
- No legal citation falls back to deterministic report.
- Unexpected prompt construction bug is not swallowed.

### Final Verification

- `python -m pytest -v`
- `python -m ruff check .`
- `python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"`

The final CLI smoke test must run without setting `INSIGHT_GRAPH_REPORTER_PROVIDER=llm` and must still produce a deterministic report with references.

## Documentation

Update `README.md` to document:

- `INSIGHT_GRAPH_REPORTER_PROVIDER=deterministic|llm`.
- Reuse of `INSIGHT_GRAPH_LLM_API_KEY`, `INSIGHT_GRAPH_LLM_BASE_URL`, and `INSIGHT_GRAPH_LLM_MODEL`.
- Default deterministic/offline behavior.
- OpenAI-compatible Reporter example command.
- Citation guardrail behavior: LLM can write report body, but References are system-generated from verified evidence.
- Tests do not call external LLMs.

Also update the MVP note that still lists LLM routing as future-only. It should say the shared OpenAI-compatible LLM layer now exists for opt-in Analyst/Reporter-style components, while broader provider routing and observability remain future work.

## Success Criteria

- Default Reporter output remains deterministic and offline.
- Opt-in LLM Reporter can generate a professional Markdown report body.
- Final References are deterministic and only include verified evidence.
- LLM output cannot introduce unsupported citation numbers or fake sources.
- Expected LLM failures fall back to deterministic Reporter.
- Tests, lint, and default CLI smoke pass.
