import pytest

from insight_graph.tools.search_providers import (
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
