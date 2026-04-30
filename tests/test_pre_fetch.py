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
        SearchResult(title="One", url="https://example.com/one", snippet="one", source="fake"),
        SearchResult(title="Two", url="https://example.com/two", snippet="two", source="fake"),
        SearchResult(
            title="Three",
            url="https://example.com/three",
            snippet="three",
            source="fake",
        ),
    ]

    evidence = pre_fetch_module.pre_fetch_results(results, "s1", limit=2)

    assert fetched_urls == ["https://example.com/one", "https://example.com/two"]
    assert [item.id for item in evidence] == ["one", "two"]
    assert all(item.subtask_id == "s1" for item in evidence)
    assert [(item.search_provider, item.search_rank) for item in evidence] == [
        ("fake", 1),
        ("fake", 2),
    ]
    assert [item.search_query for item in evidence] == [None, None]
    assert [item.search_snippet for item in evidence] == ["one", "two"]
    assert [item.fetch_status for item in evidence] == ["fetched", "fetched"]


def test_pre_fetch_results_records_empty_evidence_candidate(monkeypatch) -> None:
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

    assert [item.id for item in evidence] == [
        "fetch-missing-example-com-empty",
        "kept",
    ]
    assert evidence[0].verified is False
    assert evidence[0].source_url == "https://example.com/empty"
    assert evidence[0].fetch_status == "empty"
    assert evidence[0].fetch_error == "fetch returned no evidence"
    assert evidence[0].search_provider == "mock"
    assert evidence[0].search_rank == 1


def test_pre_fetch_results_records_fetch_error_candidate(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")

    def fake_fetch_url(url: str, subtask_id: str):
        if url.endswith("broken"):
            raise RuntimeError("fetch failed")
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
        SearchResult(title="Broken", url="https://example.com/broken", snippet="broken"),
        SearchResult(title="Kept", url="https://example.com/kept", snippet="kept"),
    ]

    evidence = pre_fetch_module.pre_fetch_results(results, "s1")

    assert [item.id for item in evidence] == [
        "fetch-failed-example-com-broken",
        "kept",
    ]
    assert evidence[0].verified is False
    assert evidence[0].source_url == "https://example.com/broken"
    assert evidence[0].fetch_status == "failed"
    assert evidence[0].fetch_error == "fetch failed"
    assert evidence[0].search_rank == 1


def test_pre_fetch_marks_diagnostic_evidence_verification_state(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")

    def fake_fetch_url(url: str, subtask_id: str):
        if url.endswith("broken"):
            raise RuntimeError("fetch failed")
        return []

    monkeypatch.setattr(pre_fetch_module, "fetch_url", fake_fetch_url)
    results = [
        SearchResult(title="Broken", url="https://github.com/sst/broken", snippet="broken"),
        SearchResult(title="Empty", url="https://example.com/empty", snippet="empty"),
    ]

    evidence = pre_fetch_module.pre_fetch_results(results, "s1", limit=2)

    assert [item.reachable for item in evidence] == [False, True]
    assert [item.source_trusted for item in evidence] == [True, False]
    assert [item.claim_supported for item in evidence] == [False, False]


def test_pre_fetch_results_respects_fetch_budget(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")
    fetched_urls = []

    def fake_fetch_url(url: str, subtask_id: str):
        fetched_urls.append(url)
        return []

    monkeypatch.setenv("INSIGHT_GRAPH_MAX_FETCHES", "1")
    monkeypatch.setattr(pre_fetch_module, "fetch_url", fake_fetch_url)
    results = [
        SearchResult(title="One", url="https://example.com/one", snippet="one"),
        SearchResult(title="Two", url="https://example.com/two", snippet="two"),
    ]

    evidence = pre_fetch_module.pre_fetch_results(results, "s1", limit=2)

    assert [item.id for item in evidence] == ["fetch-missing-example-com-one"]
    assert evidence[0].verified is False
    assert evidence[0].fetch_status == "empty"
    assert fetched_urls == ["https://example.com/one"]


def test_pre_fetch_results_passes_query_to_fetch_url(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")
    observed_queries = []

    def fake_fetch_url(url: str, subtask_id: str):
        observed_queries.append(url)
        return []

    monkeypatch.setattr(pre_fetch_module, "fetch_url", fake_fetch_url)
    results = [SearchResult(title="One", url="https://example.com/one", snippet="one")]

    evidence = pre_fetch_module.pre_fetch_results(
        results,
        "s1",
        limit=1,
        query="pricing strategy",
    )

    assert [item.id for item in evidence] == ["fetch-missing-example-com-one"]
    assert evidence[0].verified is False
    assert evidence[0].search_query == "pricing strategy"
    assert observed_queries == [
        '{"url":"https://example.com/one","query":"pricing strategy"}'
    ]


def test_pre_fetch_results_attaches_search_query_metadata(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")

    def fake_fetch_url(url: str, subtask_id: str):
        return [
            Evidence(
                id="kept",
                subtask_id=subtask_id,
                title="Kept",
                source_url="https://example.com/kept",
                snippet="Kept evidence snippet.",
                verified=True,
            )
        ]

    monkeypatch.setattr(pre_fetch_module, "fetch_url", fake_fetch_url)
    results = [
        SearchResult(
            title="Kept result",
            url="https://example.com/kept",
            snippet="Search snippet.",
            source="duckduckgo",
        )
    ]

    evidence = pre_fetch_module.pre_fetch_results(
        results,
        "s1",
        limit=1,
        query="pricing strategy",
    )

    assert evidence[0].search_query == "pricing strategy"
    assert evidence[0].search_snippet == "Search snippet."
    assert evidence[0].search_provider == "duckduckgo"


def test_pre_fetch_deduplicates_candidates_by_canonical_url(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")
    fetched_urls = []

    def fake_fetch_url(url: str, subtask_id: str):
        fetched_urls.append(url)
        return [
            Evidence(
                id="kept",
                subtask_id=subtask_id,
                title="Kept",
                source_url="https://example.com/page?utm_source=newsletter#hero",
                snippet="Kept evidence snippet.",
                verified=True,
            )
        ]

    monkeypatch.setattr(pre_fetch_module, "fetch_url", fake_fetch_url)
    results = [
        SearchResult(
            title="Tracked",
            url="https://example.com/page?utm_source=newsletter#hero",
            snippet="tracked",
        ),
        SearchResult(
            title="Canonical duplicate",
            url="https://EXAMPLE.com:443/page",
            snippet="duplicate",
        ),
    ]

    evidence = pre_fetch_module.pre_fetch_results(results, "s1", limit=2)

    assert fetched_urls == ["https://example.com/page?utm_source=newsletter#hero"]
    assert len(evidence) == 1
    assert evidence[0].canonical_url == "https://example.com/page"
