# LLM Observability Design

## Goal

Add lightweight LLM call observability to InsightGraph so live runs can explain which stage called an LLM, which provider/model was used, whether the call succeeded, how long it took, and why it failed when fallback behavior is triggered.

The default deterministic/offline workflow must remain unchanged and should not create LLM call records.

## Scope

This increment adds in-memory metadata on `GraphState`. It does not write logs to disk, persist records to a database, expose a REST API, or record prompt/response content.

## Data Model

Add a new state model:

```python
class LLMCallRecord(BaseModel):
    stage: str
    provider: str
    model: str
    success: bool
    duration_ms: int
    error: str | None = None
```

Add this field to `GraphState`:

```python
llm_call_log: list[LLMCallRecord] = Field(default_factory=list)
```

`stage` should use one of these current values:

- `relevance`
- `analyst`
- `reporter`

`provider` should match the active LLM-compatible provider name. For the current implementation this is `openai_compatible` for relevance and `llm` for Analyst/Reporter provider selection unless the implementation already has a more specific internal provider name available.

`model` should come from the resolved `LLMConfig.model`.

`duration_ms` should measure only the LLM client call duration, not deterministic fallback work.

`error` should be absent on success and contain a short, non-secret failure summary on failure. It may include exception class and message, but must not include prompts, responses, API keys, or request headers.

## Recording Behavior

LLM call records should be appended only when a real LLM call is attempted.

### Relevance

When `OpenAICompatibleRelevanceJudge` calls the LLM client, record a `stage="relevance"` entry for each evidence judgment attempt.

- On valid LLM response: `success=True`
- On API error, invalid JSON, invalid schema, or missing key failure inside the attempted LLM path: `success=False`
- Deterministic relevance judge should not append records

### Analyst

When `INSIGHT_GRAPH_ANALYST_PROVIDER=llm` attempts an LLM call, append one `stage="analyst"` record.

- On accepted LLM findings: `success=True`
- On LLM API error or invalid LLM output that triggers deterministic fallback: `success=False`
- If no API key exists and no LLM call is attempted, do not append a record
- Unexpected programming errors that intentionally propagate should still record failure if the LLM call was already attempted and failed

### Reporter

When `INSIGHT_GRAPH_REPORTER_PROVIDER=llm` attempts an LLM call, append one `stage="reporter"` record.

- On accepted LLM report body: `success=True`
- On LLM API error or invalid LLM output that triggers deterministic fallback: `success=False`
- If no API key exists and no LLM call is attempted, do not append a record
- Unexpected programming errors that intentionally propagate should still record failure if the LLM call was already attempted and failed

## Privacy and Safety

The log must not store:

- prompt text
- completion text
- raw response JSON
- API keys
- authorization headers
- full request bodies

The log may store:

- stage
- provider
- model
- success/failure
- duration in milliseconds
- short sanitized error summary

## Testing

Tests must use fake LLM clients only and must not access the network.

Add coverage for:

- `GraphState` starts with an empty `llm_call_log`
- successful LLM Analyst call appends one success record
- invalid/failing LLM Analyst call that falls back appends one failure record
- successful LLM Reporter call appends one success record
- invalid/failing LLM Reporter call that falls back appends one failure record
- OpenAI-compatible relevance judge appends success/failure records for attempted LLM judgments
- deterministic/offline default graph path does not append LLM call records
- records do not include prompt text, response text, or API key values

## Documentation

Update `README.md` to document that live LLM runs populate `GraphState.llm_call_log` with metadata only. State explicitly that prompt, response, and secret values are not stored.

## Non-Goals

- No persistent log files
- No database schema
- No token counting
- No cost estimation
- No REST or WebSocket exposure
- No prompt/response capture
- No provider adapter changes
