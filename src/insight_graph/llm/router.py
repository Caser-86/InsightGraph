from __future__ import annotations

from insight_graph.llm.client import OpenAICompatibleChatClient
from insight_graph.llm.config import LLMConfig


def get_llm_client(config: LLMConfig | None = None) -> OpenAICompatibleChatClient:
    return OpenAICompatibleChatClient(config=config)
