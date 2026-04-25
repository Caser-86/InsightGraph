from __future__ import annotations

import os

from pydantic import BaseModel


class LLMConfig(BaseModel):
    api_key: str | None
    base_url: str | None
    model: str


def resolve_llm_config(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
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
    )
