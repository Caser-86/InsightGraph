from __future__ import annotations

import os

from pydantic import BaseModel

from insight_graph.llm.client import ChatMessage, OpenAICompatibleChatClient
from insight_graph.llm.config import LLMConfig, resolve_llm_config

DEFAULT_FAST_CHAR_THRESHOLD = 2000
DEFAULT_STRONG_CHAR_THRESHOLD = 12000
LLM_ROUTER_DISABLED = ""
LLM_ROUTER_RULES = "rules"
SUPPORTED_LLM_ROUTERS = {LLM_ROUTER_DISABLED, LLM_ROUTER_RULES}


class LLMRouterDecision(BaseModel):
    router: str
    tier: str
    reason: str
    message_chars: int | None = None


def get_llm_client(
    config: LLMConfig | None = None,
    *,
    purpose: str = "default",
    messages: list[ChatMessage] | None = None,
) -> OpenAICompatibleChatClient:
    resolved = config or resolve_llm_config()
    selected_model, decision = select_llm_model_with_decision(
        resolved,
        purpose=purpose,
        messages=messages,
    )
    if selected_model != resolved.model:
        resolved = resolved.model_copy(update={"model": selected_model})
    if decision is not None:
        resolved = _apply_tier_overrides(resolved, decision.tier)
    client = OpenAICompatibleChatClient(config=resolved)
    if decision is not None:
        client.router_decision = decision
    return client


def get_llm_router_decision(llm_client: object) -> LLMRouterDecision | None:
    decision = getattr(llm_client, "router_decision", None)
    if isinstance(decision, LLMRouterDecision):
        return decision
    return None


def select_llm_model(
    config: LLMConfig,
    *,
    purpose: str = "default",
    messages: list[ChatMessage] | None = None,
) -> str:
    selected_model, _decision = select_llm_model_with_decision(
        config,
        purpose=purpose,
        messages=messages,
    )
    return selected_model


def select_llm_model_with_decision(
    config: LLMConfig,
    *,
    purpose: str = "default",
    messages: list[ChatMessage] | None = None,
) -> tuple[str, LLMRouterDecision | None]:
    router = os.getenv("INSIGHT_GRAPH_LLM_ROUTER", LLM_ROUTER_DISABLED).strip().lower()
    if router not in SUPPORTED_LLM_ROUTERS:
        raise ValueError(f"Unsupported LLM router: {router}")
    if router != LLM_ROUTER_RULES:
        return config.model, None

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

    if purpose in {"reporter", "report_review"}:
        return strong_model, LLMRouterDecision(
            router=router,
            tier="strong",
            reason=f"{purpose}_strong",
            message_chars=message_chars,
        )
    if purpose in {"analyst", "citation_judge"}:
        return default_model, LLMRouterDecision(
            router=router,
            tier="default",
            reason=f"{purpose}_default",
            message_chars=message_chars,
        )
    if message_chars is not None and message_chars > strong_threshold:
        return strong_model, LLMRouterDecision(
            router=router,
            tier="strong",
            reason="long_prompt",
            message_chars=message_chars,
        )
    if purpose == "default" and message_chars is not None and message_chars <= fast_threshold:
        return fast_model, LLMRouterDecision(
            router=router,
            tier="fast",
            reason="short_default_prompt",
            message_chars=message_chars,
        )
    return default_model, LLMRouterDecision(
        router=router,
        tier="default",
        reason="default",
        message_chars=message_chars,
    )


def _tier_model(env_name: str, fallback: str) -> str:
    return os.getenv(env_name) or fallback


def _apply_tier_overrides(config: LLMConfig, tier: str) -> LLMConfig:
    suffix = tier.upper().replace("-", "_")
    overrides: dict[str, object] = {}
    api_key = os.getenv(f"INSIGHT_GRAPH_LLM_API_KEY_{suffix}")
    base_url = os.getenv(f"INSIGHT_GRAPH_LLM_BASE_URL_{suffix}")
    wire_api = os.getenv(f"INSIGHT_GRAPH_LLM_WIRE_API_{suffix}")
    max_output_tokens = _optional_int_env(
        f"INSIGHT_GRAPH_LLM_MAX_OUTPUT_TOKENS_{suffix}"
    )
    timeout_seconds = _optional_float_env(
        f"INSIGHT_GRAPH_LLM_TIMEOUT_SECONDS_{suffix}"
    )
    if api_key:
        overrides["api_key"] = api_key
    if base_url:
        overrides["base_url"] = base_url
    if wire_api:
        overrides["wire_api"] = wire_api
    if max_output_tokens is not None:
        overrides["max_output_tokens"] = max_output_tokens
    if timeout_seconds is not None:
        overrides["timeout_seconds"] = timeout_seconds
    if not overrides:
        return config
    return config.model_copy(update=overrides)


def _optional_int_env(name: str) -> int | None:
    raw_value = os.getenv(name)
    if raw_value in {None, ""}:
        return None
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    return value if value > 0 else None


def _optional_float_env(name: str) -> float | None:
    raw_value = os.getenv(name)
    if raw_value in {None, ""}:
        return None
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    return value if value > 0 else None


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
