import importlib

import pytest

from insight_graph.state import Evidence
from insight_graph.tools import SearchResult, ToolRegistry, fetch_url, web_search
from insight_graph.tools.http_client import FetchedPage


def test_tools_package_exports_fetch_url_callable() -> None:
    assert callable(fetch_url)


def test_tools_package_exports_web_search_callable_and_search_result() -> None:
    assert callable(web_search)
    assert web_search is importlib.import_module("insight_graph.tools.web_search")

    result = SearchResult(
        title="Title",
        url="https://example.com",
        snippet="Snippet",
    )

    assert result.source == "mock"


def test_registry_runs_fetch_url_tool(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html",
            text=(
                "<html><head><title>Tool Page</title></head>"
                "<body><p>Tool evidence.</p></body></html>"
            ),
        )

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)

    evidence = ToolRegistry().run("fetch_url", "https://example.com/tool", "s1")

    assert len(evidence) == 1
    assert evidence[0].title == "Tool Page"
    assert evidence[0].verified is True


def test_registry_runs_web_search_tool(monkeypatch) -> None:
    def fake_pre_fetch_results(results, subtask_id: str, limit: int = 3):
        return [
            Evidence(
                id="web-search-evidence",
                subtask_id=subtask_id,
                source_url="https://example.com",
                title="Web Search Evidence",
                snippet="Web search excerpt.",
            )
        ]

    web_search_module = importlib.import_module("insight_graph.tools.web_search")
    monkeypatch.setattr(web_search_module, "pre_fetch_results", fake_pre_fetch_results)

    evidence = ToolRegistry().run("web_search", "Compare AI coding agents", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == "web-search-evidence"
    assert evidence[0].subtask_id == "s1"


def test_registry_unknown_tool_still_raises_key_error() -> None:
    with pytest.raises(KeyError, match="Unknown tool"):
        ToolRegistry().run("missing_tool", "query", "s1")
