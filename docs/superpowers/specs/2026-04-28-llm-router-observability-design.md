# LLM Router Observability Design

## Goal

Expose internal LLM rules router decisions in existing LLM call logs so users can verify which tier was selected and why, without logging prompts or adding a separate router log.

## Scope

- Add router decision metadata for active `INSIGHT_GRAPH_LLM_ROUTER=rules` calls.
- Surface metadata through `GraphState.llm_call_log` and JSON output.
- Keep deterministic/offline paths unchanged.
- Keep injected fake/test clients compatible.
- Avoid storing raw prompts, completions, or secrets.

## Non-goals

- No separate router decision log.
- No cost estimation.
- No provider pricing or latency metadata.
- No model classifier calls.
- No API behavior changes beyond optional JSON fields already present in `llm_call_log`.

## Recommended Approach

Attach route decision metadata to the returned LLM client.

`get_llm_client()` will compute a route decision and attach it to the returned `OpenAICompatibleChatClient` only when the rules router is active. Observability code will read that optional metadata from the client and copy it into `LLMCallRecord`.

This keeps the client factory return type unchanged and avoids global or thread-local state.

## Router Decision Shape

Add an internal decision type in `src/insight_graph/llm/router.py`:

- `router: str`
- `tier: str`
- `reason: str`
- `message_chars: int | None`

Supported tiers:

- `fast`
- `default`
- `strong`

Supported reasons:

- `short_default_prompt`
- `default`
- `long_prompt`
- `reporter_strong`

When routing is disabled, no decision metadata is attached and no router fields are logged.

## LLM Call Record Fields

Extend `LLMCallRecord` with optional fields:

- `router: str | None = None`
- `router_tier: str | None = None`
- `router_reason: str | None = None`
- `router_message_chars: int | None = None`

These fields are optional to preserve compatibility with existing tests, saved JSON output consumers, and deterministic/offline paths.

## Data Flow

1. Analyst/reporter build messages and call `get_llm_client(config, purpose=..., messages=...)`.
2. Router selects model and builds a decision when `INSIGHT_GRAPH_LLM_ROUTER=rules`.
3. Router attaches the decision to the returned client as internal metadata.
4. Agent calls the client normally.
5. Agent builds `LLMCallRecord` through `build_llm_call_record()`.
6. Observability helper reads optional router metadata from the client and copies safe fields into the record.

The log records only total prompt character count, not prompt content.

## CLI Display

`--show-llm-log` should include compact router metadata when present.

Add columns after `Model`:

- `Router`
- `Tier`
- `Reason`

For records without router metadata, display `-` in those columns. This keeps the table stable and makes routed and non-routed calls easy to compare.

## Error Handling

- Missing router metadata means no router fields in JSON and `-` in CLI table.
- Invalid router config continues to fail through existing router validation.
- If a fake client has no `router_decision`, observability remains unchanged.
- If a malformed custom client has unexpected router metadata, ignore it unless it matches the expected decision type or shape.

## Testing Requirements

Router tests:

- Rules router attaches decision metadata for fast/default/strong choices.
- Router disabled does not attach decision metadata.
- Decision includes `message_chars` when messages are provided.

Observability tests:

- `build_llm_call_record()` copies router metadata into `LLMCallRecord`.
- Missing router metadata preserves current record shape.
- Prompt content is not logged.

Agent tests:

- Analyst successful LLM call records router tier/reason when router is enabled.
- Reporter successful LLM call records router tier/reason when router is enabled.

CLI tests:

- LLM log formatting includes router columns.
- Records without router metadata render `-` in router columns.

All tests must remain deterministic and offline.

## Documentation

Update configuration docs to state that `llm_call_log` includes router metadata when `INSIGHT_GRAPH_LLM_ROUTER=rules` is enabled, and that only aggregate character counts are logged.
