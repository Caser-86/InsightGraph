import importlib

from insight_graph.state import Evidence
from insight_graph.tools.web_search import SearchResult


def test_pre_fetch_results_limits_and_flattens_evidence(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")
    fetched_urls = []

    def fake_fetch_url(url: str, subtask_id: str):
        fetched_urls.append(url)
        return [
            Evidence(
                id=url.rsplit("/", 1)[-1],
                subtask_id=subtask_id,
                title=f"Fetched {url}",
                source_url=url,
                snippet="Fetched evidence snippet.",
                verified=True,
            )
        ]

    monkeypatch.setattr(pre_fetch_module, "fetch_url", fake_fetch_url)
    results = [
        SearchResult(title="One", url="https://example.com/one", snippet="one"),
        SearchResult(title="Two", url="https://example.com/two", snippet="two"),
        SearchResult(title="Three", url="https://example.com/three", snippet="three"),
    ]

    evidence = pre_fetch_module.pre_fetch_results(results, "s1", limit=2)

    assert fetched_urls == ["https://example.com/one", "https://example.com/two"]
    assert [item.id for item in evidence] == ["one", "two"]
    assert all(item.subtask_id == "s1" for item in evidence)


def test_pre_fetch_results_skips_empty_evidence(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")

    def fake_fetch_url(url: str, subtask_id: str):
        if url.endswith("empty"):
            return []
        return [
            Evidence(
                id="kept",
                subtask_id=subtask_id,
                title="Kept",
                source_url=url,
                snippet="Kept evidence snippet.",
                verified=True,
            )
        ]

    monkeypatch.setattr(pre_fetch_module, "fetch_url", fake_fetch_url)
    results = [
        SearchResult(title="Empty", url="https://example.com/empty", snippet="empty"),
        SearchResult(title="Kept", url="https://example.com/kept", snippet="kept"),
    ]

    evidence = pre_fetch_module.pre_fetch_results(results, "s1")

    assert [item.id for item in evidence] == ["kept"]
