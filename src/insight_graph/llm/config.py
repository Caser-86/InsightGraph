from __future__ import annotations

import os

from pydantic import BaseModel, field_validator

DEFAULT_LLM_WIRE_API = "chat_completions"
SUPPORTED_LLM_WIRE_APIS = frozenset({"chat_completions", "responses"})


class LLMConfig(BaseModel):
    api_key: str | None
    base_url: str | None
    model: str
    wire_api: str = DEFAULT_LLM_WIRE_API

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
    wire_api: str | None = None,
) -> LLMConfig:
    return LLMConfig(
        api_key=api_key
        if api_key is not None
        else os.getenv("INSIGHT_GRAPH_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=base_url
        if base_url is not None
        else os.getenv("INSIGHT_GRAPH_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
        model=model
        if model is not None
        else os.getenv("INSIGHT_GRAPH_LLM_MODEL") or "gpt-4o-mini",
        wire_api=wire_api
        if wire_api is not None
        else os.getenv("INSIGHT_GRAPH_LLM_WIRE_API") or DEFAULT_LLM_WIRE_API,
    )
