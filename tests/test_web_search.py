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
