import os
from typing import Protocol

from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "mock"


class SearchProvider(Protocol):
    def search(self, query: str, limit: int) -> list[SearchResult]: ...


class MockSearchProvider:
    def search(self, query: str, limit: int) -> list[SearchResult]:
        return _mock_results()[:limit]


def get_search_provider(name: str | None = None) -> SearchProvider:
    provider_name = (name or os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")).lower()
    if provider_name == "mock":
        return MockSearchProvider()
    raise ValueError(f"Unknown search provider: {provider_name}")


def parse_search_limit(default: int = 3) -> int:
    raw_limit = os.getenv("INSIGHT_GRAPH_SEARCH_LIMIT")
    if raw_limit is None:
        return default
    try:
        limit = int(raw_limit)
    except ValueError:
        return default
    if limit <= 0:
        return default
    return limit


def _mock_results() -> list[SearchResult]:
    return [
        SearchResult(
            title="Cursor Pricing",
            url="https://cursor.com/pricing",
            snippet="Cursor pricing information for AI coding plans.",
        ),
        SearchResult(
            title="GitHub Copilot Documentation",
            url="https://docs.github.com/copilot",
            snippet="GitHub Copilot documentation and feature guides.",
        ),
        SearchResult(
            title="opencode GitHub Repository",
            url="https://github.com/sst/opencode",
            snippet="Open source agentic coding tool repository.",
        ),
    ]
