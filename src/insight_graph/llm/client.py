from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel

from insight_graph.llm.config import LLMConfig, resolve_llm_config


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionResult(BaseModel):
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ChatCompletionClient(Protocol):
    def complete_json(self, messages: list[ChatMessage]) -> str: ...

    def complete_json_with_usage(
        self,
        messages: list[ChatMessage],
    ) -> ChatCompletionResult: ...


ClientFactory = Callable[..., Any]


class OpenAICompatibleChatClient:
    def __init__(
        self,
        config: LLMConfig | None = None,
        client: Any | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.config = config or resolve_llm_config()
        self._client = client
        self._client_factory = client_factory or _create_openai_client

    def complete_json(self, messages: list[ChatMessage]) -> str:
        return self.complete_json_with_usage(messages).content

    def complete_json_with_usage(
        self,
        messages: list[ChatMessage],
    ) -> ChatCompletionResult:
        if not self.config.api_key:
            raise ValueError("LLM api_key is required")
        return self._complete_with_retry_and_fallback(messages)

    def _complete_with_retry_and_fallback(
        self,
        messages: list[ChatMessage],
    ) -> ChatCompletionResult:
        retries = max(int(self.config.max_retries), 0)
        backoff = max(float(self.config.retry_backoff_seconds), 0.0)
        last_error: Exception | None = None
        for candidate in self._candidate_configs():
            self.config = candidate
            for attempt in range(retries + 1):
                try:
                    if candidate.wire_api == "responses":
                        return self._complete_json_with_responses(messages)
                    return self._complete_json_with_chat_completions(messages)
                except Exception as exc:
                    last_error = exc
                    if attempt >= retries:
                        break
                    if backoff > 0:
                        time.sleep(backoff * (attempt + 1))
        if last_error is not None:
            raise last_error
        raise ValueError("LLM call failed.")

    def _candidate_configs(self) -> list[LLMConfig]:
        candidates = [self.config]
        seen = {self.config.model}
        for model in self.config.fallback_models:
            if model in seen:
                continue
            seen.add(model)
            candidates.append(self.config.model_copy(update={"model": model}))
        return candidates

    def _complete_json_with_chat_completions(
        self,
        messages: list[ChatMessage],
    ) -> ChatCompletionResult:
        kwargs = {
            "model": self.config.model,
            "messages": [message.model_dump() for message in messages],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        if self.config.max_output_tokens is not None:
            kwargs["max_tokens"] = self.config.max_output_tokens
        response = self._get_client().chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LLM response content is required")
        usage = getattr(response, "usage", None)
        return ChatCompletionResult(
            content=content,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )

    def _complete_json_with_responses(
        self,
        messages: list[ChatMessage],
    ) -> ChatCompletionResult:
        kwargs = {
            "model": self.config.model,
            "input": [message.model_dump() for message in messages],
            "text": {"format": {"type": "json_object"}},
            "temperature": 0,
        }
        if self.config.max_output_tokens is not None:
            kwargs["max_output_tokens"] = self.config.max_output_tokens
        response = self._get_client().responses.create(**kwargs)
        content = _extract_responses_content(response)
        usage = getattr(response, "usage", None)
        return ChatCompletionResult(
            content=content,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )

    def _get_client(self) -> Any:
        if self._client is None:
            kwargs = {"api_key": self.config.api_key}
            if self.config.base_url:
                kwargs["base_url"] = self.config.base_url
            self._client = self._client_factory(**kwargs)
        return self._client


def _create_openai_client(api_key: str, base_url: str | None = None) -> Any:
    from openai import OpenAI

    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _extract_responses_content(response: Any) -> str:
    output_text = _get_attr_or_key(response, "output_text")
    if output_text:
        return output_text

    parts: list[str] = []
    for output_item in _get_attr_or_key(response, "output") or []:
        for content_item in _get_attr_or_key(output_item, "content") or []:
            text = _get_attr_or_key(content_item, "text")
            if text:
                parts.append(text)

    content = "".join(parts)
    if content:
        return content
    raise ValueError("LLM response content is required")


def _get_attr_or_key(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)
