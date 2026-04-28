from __future__ import annotations

import os

from insight_graph.llm.client import ChatMessage, OpenAICompatibleChatClient
from insight_graph.llm.config import LLMConfig, resolve_llm_config

DEFAULT_FAST_CHAR_THRESHOLD = 2000
DEFAULT_STRONG_CHAR_THRESHOLD = 12000
LLM_ROUTER_DISABLED = ""
LLM_ROUTER_RULES = "rules"
SUPPORTED_LLM_ROUTERS = {LLM_ROUTER_DISABLED, LLM_ROUTER_RULES}


def get_llm_client(
    config: LLMConfig | None = None,
    *,
    purpose: str = "default",
    messages: list[ChatMessage] | None = None,
) -> OpenAICompatibleChatClient:
    resolved = config or resolve_llm_config()
    selected_model = select_llm_model(resolved, purpose=purpose, messages=messages)
    if selected_model != resolved.model:
        resolved = resolved.model_copy(update={"model": selected_model})
    return OpenAICompatibleChatClient(config=resolved)


def select_llm_model(
    config: LLMConfig,
    *,
    purpose: str = "default",
    messages: list[ChatMessage] | None = None,
) -> str:
    router = os.getenv("INSIGHT_GRAPH_LLM_ROUTER", LLM_ROUTER_DISABLED).strip().lower()
    if router not in SUPPORTED_LLM_ROUTERS:
        raise ValueError(f"Unsupported LLM router: {router}")
    if router != LLM_ROUTER_RULES:
        return config.model

    fast_model = _tier_model("INSIGHT_GRAPH_LLM_MODEL_FAST", config.model)
    default_model = _tier_model("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", config.model)
    strong_model = _tier_model("INSIGHT_GRAPH_LLM_MODEL_STRONG", default_model)
    message_chars = _message_char_count(messages)
    fast_threshold = _int_env(
        "INSIGHT_GRAPH_LLM_ROUTER_FAST_CHAR_THRESHOLD",
        DEFAULT_FAST_CHAR_THRESHOLD,
    )
    strong_threshold = _int_env(
        "INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD",
        DEFAULT_STRONG_CHAR_THRESHOLD,
    )

    if purpose == "reporter":
        return strong_model
    if message_chars is not None and message_chars > strong_threshold:
        return strong_model
    if purpose == "default" and message_chars is not None and message_chars <= fast_threshold:
        return fast_model
    return default_model


def _tier_model(env_name: str, fallback: str) -> str:
    return os.getenv(env_name) or fallback


def _message_char_count(messages: list[ChatMessage] | None) -> int | None:
    if messages is None:
        return None
    return sum(len(message.content) for message in messages)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value
