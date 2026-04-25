from __future__ import annotations

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

        response = self._get_client().chat.completions.create(
            model=self.config.model,
            messages=[message.model_dump() for message in messages],
            response_format={"type": "json_object"},
            temperature=0,
        )
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
