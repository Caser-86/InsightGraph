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
    def __init__(self, client_factory: Callable[..., Any] | None = None) -> None:
        self._client_factory = client_factory or _create_duckduckgo_client
        self._proxy = os.getenv("INSIGHT_GRAPH_SEARCH_PROXY") or os.getenv("DDGS_PROXY")

    def search(self, query: str, limit: int) -> list[SearchResult]:
        try:
            client = self._client_factory(proxy=self._proxy)
        except TypeError:
            try:
                client = self._client_factory()
            except Exception:
                return []
        try:
            raw_results = _run_text_search(client, query, limit)
            return _map_duckduckgo_results(raw_results)
        except Exception:
            return []


class GoogleSearchProvider:
    def __init__(self) -> None:
        self._api_key = os.getenv("INSIGHT_GRAPH_GOOGLE_API_KEY")
        self._cse_id = os.getenv("INSIGHT_GRAPH_GOOGLE_CSE_ID")

    def search(self, query: str, limit: int) -> list[SearchResult]:
        if not self._api_key or not self._cse_id:
            return []
        try:
            return _call_google_search(query, limit, self._api_key, self._cse_id)
        except Exception:
            return []


class SerpAPISearchProvider:
    def __init__(self) -> None:
        self._api_key = (
            os.getenv("INSIGHT_GRAPH_SERPAPI_KEY")
            or os.getenv("INSIGHT_GRAPH_SERPAPI_API_KEY")
            or os.getenv("SERPAPI_API_KEY")
        )

    def search(self, query: str, limit: int) -> list[SearchResult]:
        if not self._api_key:
            return []
        try:
            return _call_serpapi_search(query, limit, self._api_key)
        except Exception:
            return []


def get_search_provider(name: str | None = None) -> SearchProvider:
    provider_name = (name or os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")).lower()
    if provider_name == "mock":
        return MockSearchProvider()
    if provider_name == "duckduckgo":
        return DuckDuckGoSearchProvider()
    if provider_name == "google":
        return GoogleSearchProvider()
    if provider_name == "serpapi":
        return SerpAPISearchProvider()
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


def _create_duckduckgo_client(proxy: str | None = None) -> Any:
    from ddgs import DDGS

    effective_proxy = proxy or os.getenv("INSIGHT_GRAPH_SEARCH_PROXY") or os.getenv("DDGS_PROXY")
    kwargs = {"proxy": effective_proxy} if effective_proxy else {}
    return DDGS(**kwargs)


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


def _call_google_search(
    query: str, limit: int, api_key: str, cse_id: str
) -> list[SearchResult]:
    import json
    import urllib.parse
    import urllib.request

    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": min(limit, 10),
    }
    url = f"https://www.googleapis.com/customsearch/v1?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    items = data.get("items", [])
    results: list[SearchResult] = []
    for item in items:
        link = item.get("link")
        if not link:
            continue
        results.append(
            SearchResult(
                title=item.get("title", link),
                url=link,
                snippet=item.get("snippet", ""),
                source="google",
            )
        )
    return results


def _call_serpapi_search(query: str, limit: int, api_key: str) -> list[SearchResult]:
    import json
    import urllib.parse
    import urllib.request

    params = {
        "api_key": api_key,
        "q": query,
        "engine": os.getenv("INSIGHT_GRAPH_SERPAPI_ENGINE", "google"),
        "num": min(limit, 10),
    }
    url = f"https://serpapi.com/search?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    organic_results = data.get("organic_results", [])
    results: list[SearchResult] = []
    for item in organic_results:
        link = item.get("link")
        if not link:
            continue
        results.append(
            SearchResult(
                title=item.get("title", link),
                url=link,
                snippet=item.get("snippet", ""),
                source="serpapi",
            )
        )
    return results
