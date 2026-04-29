from __future__ import annotations

import os

from pydantic import BaseModel, field_validator

DEFAULT_LLM_PROVIDER = "openai_compatible"
DEFAULT_LLM_WIRE_API = "chat_completions"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
SUPPORTED_LLM_WIRE_APIS = frozenset({"chat_completions", "responses"})

LLM_PROVIDER_PRESETS = {
    DEFAULT_LLM_PROVIDER: {
        "base_url": None,
        "model": DEFAULT_LLM_MODEL,
        "api_key": None,
        "api_key_env": None,
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2",
        "api_key": "ollama",
        "api_key_env": None,
    },
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "model": "local-model",
        "api_key": "lm-studio",
        "api_key_env": None,
    },
    "vllm": {
        "base_url": "http://localhost:8000/v1",
        "model": "local-model",
        "api_key": "vllm",
        "api_key_env": None,
    },
    "localai": {
        "base_url": "http://localhost:8080/v1",
        "model": "local-model",
        "api_key": "localai",
        "api_key_env": None,
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "api_key": None,
        "api_key_env": "DASHSCOPE_API_KEY",
    },
}
SUPPORTED_LLM_PROVIDERS = frozenset(LLM_PROVIDER_PRESETS)


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
        provider
        if provider is not None
        else os.getenv("INSIGHT_GRAPH_LLM_PROVIDER") or DEFAULT_LLM_PROVIDER
    )
    preset = LLM_PROVIDER_PRESETS.get(resolved_provider, {})
    provider_api_key_env = preset.get("api_key_env")
    provider_api_key = (
        os.getenv(provider_api_key_env)
        if isinstance(provider_api_key_env, str)
        else preset.get("api_key")
    )
    provider_base_url = preset.get("base_url")
    if resolved_provider == DEFAULT_LLM_PROVIDER:
        provider_base_url = os.getenv("OPENAI_BASE_URL")
    openai_api_key = (
        os.getenv("OPENAI_API_KEY") if resolved_provider == DEFAULT_LLM_PROVIDER else None
    )

    return LLMConfig(
        api_key=api_key
        if api_key is not None
        else os.getenv("INSIGHT_GRAPH_LLM_API_KEY")
        or provider_api_key
        or openai_api_key,
        base_url=base_url
        if base_url is not None
        else os.getenv("INSIGHT_GRAPH_LLM_BASE_URL")
        or provider_base_url,
        model=model
        if model is not None
        else os.getenv("INSIGHT_GRAPH_LLM_MODEL")
        or str(preset.get("model", DEFAULT_LLM_MODEL)),
        provider=resolved_provider,
        wire_api=wire_api
        if wire_api is not None
        else os.getenv("INSIGHT_GRAPH_LLM_WIRE_API") or DEFAULT_LLM_WIRE_API,
    )
