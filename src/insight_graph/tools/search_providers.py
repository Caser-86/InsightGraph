import os
from collections.abc import Callable, Iterable
from typing import Any, Protocol

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


class DuckDuckGoSearchProvider:
    def __init__(self, client_factory: Callable[[], Any] | None = None) -> None:
        self._client_factory = client_factory or _create_duckduckgo_client

    def search(self, query: str, limit: int) -> list[SearchResult]:
        try:
            client = self._client_factory()
            raw_results = _run_text_search(client, query, limit)
            return _map_duckduckgo_results(raw_results)
        except Exception:
            return []


def get_search_provider(name: str | None = None) -> SearchProvider:
    provider_name = (name or os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")).lower()
    if provider_name == "mock":
        return MockSearchProvider()
    if provider_name == "duckduckgo":
        return DuckDuckGoSearchProvider()
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


def _create_duckduckgo_client() -> Any:
    from duckduckgo_search import DDGS

    return DDGS()


def _run_text_search(client: Any, query: str, limit: int) -> Iterable[dict[str, Any]]:
    if hasattr(client, "__enter__"):
        with client as active_client:
            return active_client.text(query, max_results=limit)
    return client.text(query, max_results=limit)


def _map_duckduckgo_results(raw_results: Iterable[dict[str, Any]]) -> list[SearchResult]:
    results: list[SearchResult] = []
    for raw in raw_results:
        url = raw.get("href") or raw.get("url") or raw.get("link")
        if not url:
            continue
        results.append(
            SearchResult(
                title=raw.get("title") or url,
                url=url,
                snippet=raw.get("body") or raw.get("snippet") or "",
                source="duckduckgo",
            )
        )
    return results


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
