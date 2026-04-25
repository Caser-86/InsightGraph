from __future__ import annotations

from insight_graph.llm.client import ChatCompletionClient, ChatCompletionResult, ChatMessage
from insight_graph.state import LLMCallRecord


def build_llm_call_record(
    *,
    stage: str,
    provider: str,
    model: str,
    success: bool,
    duration_ms: int,
    error: Exception | None = None,
    secrets: list[str | None] | None = None,
    wire_api: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> LLMCallRecord:
    return LLMCallRecord(
        stage=stage,
        provider=provider,
        model=model,
        wire_api=wire_api,
        success=success,
        duration_ms=max(duration_ms, 0),
        input_tokens=_normalize_token_count(input_tokens),
        output_tokens=_normalize_token_count(output_tokens),
        total_tokens=_normalize_token_count(total_tokens),
        error=_summarize_error(error, secrets or []) if error is not None else None,
    )


def complete_json_with_observability(
    llm_client: ChatCompletionClient,
    messages: list[ChatMessage],
) -> ChatCompletionResult:
    complete_with_usage = getattr(llm_client, "complete_json_with_usage", None)
    if complete_with_usage is not None:
        return complete_with_usage(messages)
    return ChatCompletionResult.model_construct(content=llm_client.complete_json(messages))


def get_llm_wire_api(llm_client: ChatCompletionClient) -> str | None:
    return getattr(getattr(llm_client, "config", None), "wire_api", None)


def _normalize_token_count(value: int | None) -> int | None:
    if value is None or value < 0:
        return None
    return value


def _summarize_error(error: Exception, secrets: list[str | None]) -> str:
    return f"{type(error).__name__}: LLM call failed."
