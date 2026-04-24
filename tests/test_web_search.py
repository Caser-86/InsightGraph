from insight_graph.state import Evidence
from insight_graph.tools import web_search as web_search_module
from insight_graph.tools.web_search import SearchResult


def test_mock_web_search_returns_deterministic_results() -> None:
    results = web_search_module.mock_web_search("agentic coding tools")

    assert [result.url for result in results] == [
        "https://cursor.com/pricing",
        "https://docs.github.com/copilot",
        "https://github.com/sst/opencode",
    ]
    assert all(isinstance(result, SearchResult) for result in results)
    assert all(result.source == "mock" for result in results)


def test_web_search_prefetches_results(monkeypatch) -> None:
    captured = {}

    def fake_pre_fetch_results(results, subtask_id: str, limit: int):
        captured["urls"] = [result.url for result in results]
        captured["subtask_id"] = subtask_id
        captured["limit"] = limit
        return [
            Evidence(
                id="prefetched",
                subtask_id=subtask_id,
                title="Prefetched",
                source_url="https://example.com/prefetched",
                snippet="Prefetched evidence.",
                verified=True,
            )
        ]

    monkeypatch.setattr(web_search_module, "pre_fetch_results", fake_pre_fetch_results)

    evidence = web_search_module.web_search("agentic coding tools", subtask_id="s1")

    assert captured == {
        "urls": [
            "https://cursor.com/pricing",
            "https://docs.github.com/copilot",
            "https://github.com/sst/opencode",
        ],
        "subtask_id": "s1",
        "limit": 3,
    }
    assert [item.id for item in evidence] == ["prefetched"]


def test_web_search_uses_configured_provider_and_limit(monkeypatch) -> None:
    captured = {}

    class FakeProvider:
        def search(self, query: str, limit: int):
            captured["provider_query"] = query
            captured["provider_limit"] = limit
            return [
                SearchResult(
                    title="One",
                    url="https://example.com/one",
                    snippet="one",
                    source="fake",
                ),
                SearchResult(
                    title="Two",
                    url="https://example.com/two",
                    snippet="two",
                    source="fake",
                ),
            ]

    def fake_pre_fetch_results(results, subtask_id: str, limit: int):
        captured["prefetch_urls"] = [result.url for result in results]
        captured["subtask_id"] = subtask_id
        captured["prefetch_limit"] = limit
        return [
            Evidence(
                id="provider-prefetched",
                subtask_id=subtask_id,
                title="Provider Prefetched",
                source_url="https://example.com/one",
                snippet="Provider prefetched evidence.",
                verified=True,
            )
        ]

    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_LIMIT", "2")
    monkeypatch.setattr(web_search_module, "get_search_provider", lambda: FakeProvider())
    monkeypatch.setattr(web_search_module, "pre_fetch_results", fake_pre_fetch_results)

    evidence = web_search_module.web_search("agentic coding tools", subtask_id="s1")

    assert captured == {
        "provider_query": "agentic coding tools",
        "provider_limit": 2,
        "prefetch_urls": ["https://example.com/one", "https://example.com/two"],
        "subtask_id": "s1",
        "prefetch_limit": 2,
    }
    assert [item.id for item in evidence] == ["provider-prefetched"]
