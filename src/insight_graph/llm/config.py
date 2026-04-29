from __future__ import annotations

import os

from pydantic import BaseModel, field_validator

DEFAULT_LLM_PROVIDER = "openai_compatible"
QWEN_LLM_PROVIDER = "qwen"
SUPPORTED_LLM_PROVIDERS = frozenset({DEFAULT_LLM_PROVIDER, QWEN_LLM_PROVIDER})
QWEN_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_DEFAULT_MODEL = "qwen-plus"
DEFAULT_LLM_WIRE_API = "chat_completions"
SUPPORTED_LLM_WIRE_APIS = frozenset({"chat_completions", "responses"})


class LLMConfig(BaseModel):
    api_key: str | None
    base_url: str | None
    model: str
    provider: str = DEFAULT_LLM_PROVIDER
    wire_api: str = DEFAULT_LLM_WIRE_API

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        if value not in SUPPORTED_LLM_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_LLM_PROVIDERS))
            raise ValueError(
                f"Unsupported provider: {value}. Supported values: {supported}"
            )
        return value

    @field_validator("wire_api")
    @classmethod
    def validate_wire_api(cls, value: str) -> str:
        if value not in SUPPORTED_LLM_WIRE_APIS:
            supported = ", ".join(sorted(SUPPORTED_LLM_WIRE_APIS))
            raise ValueError(
                f"Unsupported wire_api: {value}. Supported values: {supported}"
            )
        return value


def resolve_llm_config(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    wire_api: str | None = None,
) -> LLMConfig:
    resolved_provider = (
        provider or os.getenv("INSIGHT_GRAPH_LLM_PROVIDER") or DEFAULT_LLM_PROVIDER
    )
    qwen_selected = resolved_provider == QWEN_LLM_PROVIDER

    return LLMConfig(
        api_key=api_key
        if api_key is not None
        else os.getenv("INSIGHT_GRAPH_LLM_API_KEY")
        or (os.getenv("DASHSCOPE_API_KEY") if qwen_selected else None)
        or os.getenv("OPENAI_API_KEY"),
        base_url=base_url
        if base_url is not None
        else os.getenv("INSIGHT_GRAPH_LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or (QWEN_DASHSCOPE_BASE_URL if qwen_selected else None),
        model=model
        if model is not None
        else os.getenv("INSIGHT_GRAPH_LLM_MODEL")
        or (QWEN_DEFAULT_MODEL if qwen_selected else "gpt-4o-mini"),
        provider=resolved_provider,
        wire_api=wire_api
        if wire_api is not None
        else os.getenv("INSIGHT_GRAPH_LLM_WIRE_API") or DEFAULT_LLM_WIRE_API,
    )
