import pytest

from insight_graph.tools.search_providers import (
    DuckDuckGoSearchProvider,
    MockSearchProvider,
    SearchResult,
    get_search_provider,
    parse_search_limit,
)


def test_mock_search_provider_returns_deterministic_results() -> None:
    results = MockSearchProvider().search("Compare AI coding agents", limit=2)

    assert [result.url for result in results] == [
        "https://cursor.com/pricing",
        "https://docs.github.com/copilot",
    ]
    assert all(isinstance(result, SearchResult) for result in results)
    assert all(result.source == "mock" for result in results)


def test_get_search_provider_defaults_to_mock(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_SEARCH_PROVIDER", raising=False)

    provider = get_search_provider()

    assert isinstance(provider, MockSearchProvider)


def test_get_search_provider_accepts_explicit_mock() -> None:
    provider = get_search_provider("mock")

    assert isinstance(provider, MockSearchProvider)


def test_get_search_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown search provider"):
        get_search_provider("unknown")


def test_parse_search_limit_reads_valid_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_LIMIT", "5")

    assert parse_search_limit() == 5


def test_parse_search_limit_falls_back_for_invalid_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_LIMIT", "not-a-number")

    assert parse_search_limit() == 3


def test_parse_search_limit_falls_back_for_non_positive_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_LIMIT", "0")

    assert parse_search_limit() == 3

class FakeDuckDuckGoClient:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def text(self, query: str, max_results: int):
        self.calls.append((query, max_results))
        return self.results


def test_get_search_provider_accepts_explicit_duckduckgo() -> None:
    provider = get_search_provider("duckduckgo")

    assert isinstance(provider, DuckDuckGoSearchProvider)


def test_get_search_provider_reads_duckduckgo_from_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "duckduckgo")

    provider = get_search_provider()

    assert isinstance(provider, DuckDuckGoSearchProvider)


def test_duckduckgo_provider_maps_results() -> None:
    client = FakeDuckDuckGoClient(
        [
            {
                "title": "Cursor Pricing",
                "href": "https://cursor.com/pricing",
                "body": "Cursor pricing details.",
            },
            {
                "title": "GitHub Copilot",
                "url": "https://docs.github.com/copilot",
                "snippet": "GitHub Copilot docs.",
            },
            {
                "title": "Missing URL",
                "body": "This result should be skipped.",
            },
        ]
    )
    provider = DuckDuckGoSearchProvider(client_factory=lambda: client)

    results = provider.search("AI coding agents", limit=3)

    assert client.calls == [("AI coding agents", 3)]
    assert [result.url for result in results] == [
        "https://cursor.com/pricing",
        "https://docs.github.com/copilot",
    ]
    assert [result.title for result in results] == ["Cursor Pricing", "GitHub Copilot"]
    assert [result.snippet for result in results] == [
        "Cursor pricing details.",
        "GitHub Copilot docs.",
    ]
    assert all(result.source == "duckduckgo" for result in results)


def test_duckduckgo_provider_supports_link_field() -> None:
    client = FakeDuckDuckGoClient(
        [
            {
                "title": "OpenCode",
                "link": "https://github.com/sst/opencode",
                "body": "OpenCode repository.",
            }
        ]
    )
    provider = DuckDuckGoSearchProvider(client_factory=lambda: client)

    results = provider.search("OpenCode", limit=1)

    assert [result.url for result in results] == ["https://github.com/sst/opencode"]


def test_duckduckgo_provider_returns_empty_list_on_failure() -> None:
    def broken_client_factory():
        raise RuntimeError("network unavailable")

    provider = DuckDuckGoSearchProvider(client_factory=broken_client_factory)

    assert provider.search("AI coding agents", limit=3) == []
