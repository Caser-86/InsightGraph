from insight_graph.state import Evidence
from insight_graph.tools import search_providers
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

    def fake_pre_fetch_results(results, subtask_id: str, limit: int, query: str | None = None):
        captured["urls"] = [result.url for result in results]
        captured["subtask_id"] = subtask_id
        captured["limit"] = limit
        captured["query"] = query
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

    monkeypatch.delenv("INSIGHT_GRAPH_SEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_SEARCH_LIMIT", raising=False)
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
        "query": "agentic coding tools",
    }
    assert [item.id for item in evidence] == ["prefetched"]


def test_web_search_uses_configured_provider_and_limit(monkeypatch) -> None:
    captured = {}

    def fake_search_with_providers(query: str, limit: int, provider_expression=None):
        captured["provider_query"] = query
        captured["provider_limit"] = limit
        captured["provider_expression"] = provider_expression
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

    def fake_pre_fetch_results(results, subtask_id: str, limit: int, query: str | None = None):
        captured["prefetch_urls"] = [result.url for result in results]
        captured["subtask_id"] = subtask_id
        captured["prefetch_limit"] = limit
        captured["query"] = query
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
    monkeypatch.setattr(web_search_module, "search_with_providers", fake_search_with_providers)
    monkeypatch.setattr(web_search_module, "pre_fetch_results", fake_pre_fetch_results)

    evidence = web_search_module.web_search("agentic coding tools", subtask_id="s1")

    assert captured == {
        "provider_query": "agentic coding tools",
        "provider_limit": 2,
        "provider_expression": None,
        "prefetch_urls": ["https://example.com/one", "https://example.com/two"],
        "subtask_id": "s1",
        "prefetch_limit": 2,
        "query": "agentic coding tools",
    }
    assert [item.id for item in evidence] == ["provider-prefetched"]


def test_serpapi_provider_accepts_common_api_key_env_aliases(monkeypatch) -> None:
    captured = {}

    def fake_call(query: str, limit: int, api_key: str):
        captured["query"] = query
        captured["limit"] = limit
        captured["api_key"] = api_key
        return [
            SearchResult(
                title="SerpAPI result",
                url="https://example.com/serpapi",
                snippet="Search result from SerpAPI.",
                source="serpapi",
            )
        ]

    monkeypatch.delenv("INSIGHT_GRAPH_SERPAPI_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_SERPAPI_API_KEY", raising=False)
    monkeypatch.setenv("SERPAPI_API_KEY", "alias-key")
    monkeypatch.setattr(search_providers, "_call_serpapi_search", fake_call)

    provider = search_providers.get_search_provider("serpapi")
    results = provider.search("OpenAI strategy", limit=7)

    assert captured == {
        "query": "OpenAI strategy",
        "limit": 7,
        "api_key": "alias-key",
    }
    assert results[0].source == "serpapi"


def test_serpapi_news_provider_uses_google_news_engine(monkeypatch) -> None:
    captured = {}

    def fake_call(query: str, limit: int, api_key: str):
        captured["query"] = query
        captured["limit"] = limit
        captured["api_key"] = api_key
        return [
            SearchResult(
                title="Xiaomi SU7 delivery update",
                url="https://example.com/xiaomi-su7",
                snippet="Recent Xiaomi auto delivery news.",
                source="serpapi_news",
            )
        ]

    monkeypatch.setenv("INSIGHT_GRAPH_SERPAPI_KEY", "serp-key")
    monkeypatch.setattr(search_providers, "_call_serpapi_news_search", fake_call)

    provider = search_providers.get_news_search_provider("serpapi")
    results = provider.search("Xiaomi SU7", limit=5)

    assert captured == {
        "query": "Xiaomi SU7",
        "limit": 5,
        "api_key": "serp-key",
    }
    assert results[0].source == "serpapi_news"


def test_serpapi_news_call_uses_google_news_engine_by_default(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return (
                b'{"news_results":[{"title":"Xiaomi SU7","link":"https://example.com/su7",'
                b'"snippet":"Recent delivery news."}]}'
            )

    def fake_urlopen(request, timeout: int):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.delenv("INSIGHT_GRAPH_SERPAPI_NEWS_ENGINE", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    results = search_providers._call_serpapi_news_search("Xiaomi auto", 25, "secret-key")

    assert "engine=google_news" in captured["url"]
    assert "q=Xiaomi+auto" in captured["url"]
    assert "num=10" in captured["url"]
    assert "api_key=secret-key" in captured["url"]
    assert captured["timeout"] == 30
    assert results[0].source == "serpapi_news"


def test_serpapi_news_call_passes_min_year_filter(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"news_results":[]}'

    def fake_urlopen(request, timeout: int):
        captured["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_MIN_YEAR", "2024")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    search_providers._call_serpapi_news_search("Xiaomi auto", 5, "secret-key")

    assert "as_ylo=2024" in captured["url"]
