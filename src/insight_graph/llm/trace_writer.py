import json
import os
from pathlib import Path
from typing import Any

from insight_graph.llm import ChatCompletionClient, ChatMessage, resolve_llm_config
from insight_graph.llm.trace_export import build_full_trace_event

LLM_TRACE_ENV = "INSIGHT_GRAPH_LLM_TRACE"
LLM_TRACE_PATH_ENV = "INSIGHT_GRAPH_LLM_TRACE_PATH"
LLM_TRACE_FULL_ENV = "INSIGHT_GRAPH_LLM_TRACE_FULL"
DEFAULT_TRACE_PATH = Path("llm_logs/llm-trace.jsonl")


def is_llm_trace_enabled() -> bool:
    return bool(os.environ.get(LLM_TRACE_PATH_ENV)) or os.environ.get(
        LLM_TRACE_ENV, ""
    ).lower() in {"1", "true", "yes"}


def resolve_llm_trace_path() -> Path:
    raw_path = os.environ.get(LLM_TRACE_PATH_ENV)
    return Path(raw_path) if raw_path else DEFAULT_TRACE_PATH


def include_full_llm_trace_payload() -> bool:
    return os.environ.get(LLM_TRACE_FULL_ENV, "").strip().lower() in {"1", "true", "yes"}


def write_llm_trace_event(event: dict[str, Any]) -> None:
    if not is_llm_trace_enabled():
        return
    path = resolve_llm_trace_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def write_full_llm_trace_event(
    *,
    stage: str,
    llm_client: ChatCompletionClient,
    messages: list[ChatMessage],
    output_text: str,
    duration_ms: int,
    success: bool,
    error: Exception | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> None:
    model = getattr(getattr(llm_client, "config", None), "model", resolve_llm_config().model)
    api_key = getattr(getattr(llm_client, "config", None), "api_key", None)
    include_payload = include_full_llm_trace_payload()
    event = build_full_trace_event(
        stage=stage,
        provider="llm",
        model=model,
        messages=_redact_messages(messages, api_key),
        output_text=_redact_text(output_text, api_key),
        token_usage={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        },
        include_payload=include_payload,
    )
    event["duration_ms"] = max(duration_ms, 0)
    event["success"] = success
    if error is not None:
        event["error"] = f"{type(error).__name__}: LLM call failed."
    write_llm_trace_event(event)


def _redact_messages(messages: list[ChatMessage], secret: str | None) -> list[dict[str, str]]:
    return [
        {**message.model_dump(), "content": _redact_text(message.content, secret)}
        for message in messages
    ]


def _redact_text(value: str, secret: str | None) -> str:
    redacted = value
    if secret:
        redacted = redacted.replace(secret, "[REDACTED]")
    return redacted
