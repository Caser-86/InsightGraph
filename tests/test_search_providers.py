import pytest

from insight_graph.tools.search_providers import (
    DuckDuckGoSearchProvider,
    MockSearchProvider,
    SearchResult,
    SerpAPISearchProvider,
    _create_duckduckgo_client,
    get_search_quota_snapshot,
    get_search_provider,
    parse_search_limit,
    resolve_search_providers,
    search_with_providers,
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


def test_resolve_search_providers_supports_all() -> None:
    assert resolve_search_providers("all") == ["duckduckgo", "serpapi", "google"]


def test_resolve_search_providers_supports_comma_and_dedup() -> None:
    assert resolve_search_providers("serpapi,duckduckgo,serpapi") == [
        "serpapi",
        "duckduckgo",
    ]


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


def test_create_duckduckgo_client_uses_ddgs_package() -> None:
    client = _create_duckduckgo_client()

    assert type(client).__module__.startswith("ddgs")


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


def test_search_with_providers_round_robins_and_dedupes(monkeypatch) -> None:
    class FakeProvider:
        def __init__(self, name: str):
            self.name = name

        def search(self, query: str, limit: int):
            if self.name == "duckduckgo":
                return [
                    SearchResult(
                        title="A1",
                        url="https://example.com/a1",
                        snippet="a1",
                        source="duckduckgo",
                    ),
                    SearchResult(
                        title="A2",
                        url="https://example.com/a2",
                        snippet="a2",
                        source="duckduckgo",
                    ),
                ]
            return [
                SearchResult(
                    title="B1",
                    url="https://example.com/b1",
                    snippet="b1",
                    source="serpapi",
                ),
                SearchResult(
                    title="Dup",
                    url="https://example.com/a2",
                    snippet="dup",
                    source="serpapi",
                ),
            ]

    monkeypatch.setattr(
        "insight_graph.tools.search_providers.get_search_provider",
        lambda name=None: FakeProvider(name or "mock"),
    )

    results = search_with_providers(
        "query",
        4,
        provider_expression="duckduckgo,serpapi",
    )

    assert [item.url for item in results] == [
        "https://example.com/a1",
        "https://example.com/b1",
        "https://example.com/a2",
    ]


def test_search_with_providers_filters_blocklisted_domains(monkeypatch) -> None:
    class FakeProvider:
        def search(self, query: str, limit: int):
            return [
                SearchResult(
                    title="Blocked",
                    url="https://blocked.example.com/post",
                    snippet="recent 2026 update",
                    source="fake",
                ),
                SearchResult(
                    title="Allowed",
                    url="https://allowed.example.com/post",
                    snippet="recent 2026 update",
                    source="fake",
                ),
            ]

    monkeypatch.setenv("INSIGHT_GRAPH_SOURCE_DOMAIN_BLOCKLIST", "blocked.example.com")
    monkeypatch.setattr(
        "insight_graph.tools.search_providers.get_search_provider",
        lambda name=None: FakeProvider(),
    )

    results = search_with_providers("query", 5, provider_expression="duckduckgo")

    assert [item.url for item in results] == ["https://allowed.example.com/post"]


def test_search_with_providers_filters_old_year_results(monkeypatch) -> None:
    class FakeProvider:
        def search(self, query: str, limit: int):
            return [
                SearchResult(
                    title="Old",
                    url="https://example.com/old",
                    snippet="Market update from 2019.",
                    source="fake",
                ),
                SearchResult(
                    title="New",
                    url="https://example.com/new",
                    snippet="Market update from 2026.",
                    source="fake",
                ),
            ]

    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_MIN_YEAR", "2024")
    monkeypatch.setattr(
        "insight_graph.tools.search_providers.get_search_provider",
        lambda name=None: FakeProvider(),
    )

    results = search_with_providers("query", 5, provider_expression="duckduckgo")

    assert [item.url for item in results] == ["https://example.com/new"]


def test_serpapi_daily_call_limit_blocks_second_call(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_SERPAPI_KEY", "key")
    monkeypatch.setenv("INSIGHT_GRAPH_SERPAPI_DAILY_CALL_LIMIT", "1")
    monkeypatch.setattr(
        "insight_graph.tools.search_providers._call_serpapi_search",
        lambda query, limit, api_key: [
            SearchResult(
                title="Result",
                url="https://example.com/r",
                snippet="2026 signal",
                source="serpapi",
            )
        ],
    )
    from insight_graph.tools import search_providers as module

    module._PROVIDER_DAILY_CALL_USAGE.clear()
    provider = SerpAPISearchProvider()

    first = provider.search("query", 3)
    second = provider.search("query", 3)

    assert len(first) == 1
    assert second == []


def test_serpapi_per_run_limit_caps_effective_limit(monkeypatch) -> None:
    captured = {}

    def fake_call(query: str, limit: int, api_key: str):
        captured["limit"] = limit
        return []

    monkeypatch.setenv("INSIGHT_GRAPH_SERPAPI_KEY", "key")
    monkeypatch.setenv("INSIGHT_GRAPH_SERPAPI_PER_RUN_LIMIT", "2")
    monkeypatch.setattr("insight_graph.tools.search_providers._call_serpapi_search", fake_call)

    provider = SerpAPISearchProvider()
    provider.search("query", 9)

    assert captured["limit"] == 2


def test_get_search_quota_snapshot_includes_provider_limits(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_SERPAPI_DAILY_CALL_LIMIT", "10")
    snapshot = get_search_quota_snapshot()

    assert snapshot["serpapi"]["daily_call_limit"] == 10
    assert "date_utc" in snapshot
