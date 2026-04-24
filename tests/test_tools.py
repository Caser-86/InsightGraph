import pytest

from insight_graph.tools import ToolRegistry
from insight_graph.tools.http_client import FetchedPage


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

    monkeypatch.setattr("insight_graph.tools.fetch_url.fetch_text", fake_fetch_text)

    evidence = ToolRegistry().run("fetch_url", "https://example.com/tool", "s1")

    assert len(evidence) == 1
    assert evidence[0].title == "Tool Page"
    assert evidence[0].verified is True


def test_registry_unknown_tool_still_raises_key_error() -> None:
    with pytest.raises(KeyError, match="Unknown tool"):
        ToolRegistry().run("missing_tool", "query", "s1")
