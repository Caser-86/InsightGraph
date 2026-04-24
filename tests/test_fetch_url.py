from insight_graph.tools.fetch_url import fetch_url, infer_source_type
from insight_graph.tools.http_client import FetchedPage


def test_fetch_url_returns_verified_evidence(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        assert url == "https://example.com/product"
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text="""
            <html>
              <head><title>Example Product</title></head>
              <body><main><p>Example product evidence text.</p></main></body>
            </html>
            """,
        )

    monkeypatch.setattr("insight_graph.tools.fetch_url.fetch_text", fake_fetch_text)

    evidence = fetch_url("https://example.com/product", "s1")

    assert len(evidence) == 1
    item = evidence[0]
    assert item.id == "example-com-product"
    assert item.subtask_id == "s1"
    assert item.title == "Example Product"
    assert item.source_url == "https://example.com/product"
    assert item.snippet == "Example product evidence text."
    assert item.source_type == "unknown"
    assert item.verified is True


def test_fetch_url_returns_empty_list_for_empty_snippet(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        return FetchedPage(url=url, status_code=200, content_type="text/html", text="<html></html>")

    monkeypatch.setattr("insight_graph.tools.fetch_url.fetch_text", fake_fetch_text)

    assert fetch_url("https://example.com/empty", "s1") == []


def test_infer_source_type_from_url() -> None:
    assert infer_source_type("https://github.com/sst/opencode") == "github"
    assert infer_source_type("https://docs.github.com/copilot") == "docs"
    assert infer_source_type("https://example.com/docs/product") == "docs"
    assert infer_source_type("https://example.com/product") == "unknown"
