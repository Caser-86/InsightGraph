import hashlib
import importlib
import re

import pytest

from insight_graph.state import Evidence
from insight_graph.tools import (
    SearchResult,
    ToolRegistry,
    document_reader,
    fetch_url,
    github_search,
    news_search,
    web_search,
)
from insight_graph.tools.http_client import FetchedPage


def document_id_for(relative_path: str) -> str:
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", relative_path.lower()).strip("-")
    return f"document-{slug or 'document'}-{digest}"


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


def test_tools_package_exports_github_search_callable() -> None:
    assert callable(github_search)


def test_tools_package_exports_news_search_callable() -> None:
    assert callable(news_search)


def test_tools_package_exports_document_reader_callable() -> None:
    assert callable(document_reader)


def test_github_search_returns_deterministic_verified_github_evidence() -> None:
    evidence = github_search("Compare Cursor, OpenCode, and GitHub Copilot", "s1")

    assert len(evidence) == 3
    assert [item.id for item in evidence] == [
        "github-opencode-repository",
        "github-copilot-docs-content",
        "github-ai-coding-assistant-ecosystem",
    ]
    assert {item.subtask_id for item in evidence} == {"s1"}
    assert all(item.verified for item in evidence)
    assert all(item.source_type == "github" for item in evidence)
    assert [item.source_url for item in evidence] == [
        "https://github.com/sst/opencode",
        "https://github.com/github/docs/tree/main/content/copilot",
        "https://github.com/safishamsi/graphify",
    ]


def test_news_search_returns_deterministic_verified_news_evidence() -> None:
    evidence = news_search("AI coding agent funding", "s1")

    assert len(evidence) == 3
    assert [item.id for item in evidence] == [
        "news-github-copilot-changelog",
        "news-openai-codex-update",
        "news-cursor-changelog",
    ]
    assert {item.subtask_id for item in evidence} == {"s1"}
    assert all(item.verified for item in evidence)
    assert [item.source_type for item in evidence] == [
        "news",
        "news",
        "news",
    ]
    assert [item.source_url for item in evidence] == [
        "https://github.blog/changelog/",
        "https://openai.com/index/introducing-codex/",
        "https://www.cursor.com/changelog",
    ]


def test_document_reader_returns_verified_docs_evidence(tmp_path, monkeypatch) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    document = docs_dir / "Market Report.md"
    document.write_text(
        "# Market Report\n\nCursor   launches features.\nGitHub Copilot updates docs.",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("docs/Market Report.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == document_id_for("docs/Market Report.md")
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "Market Report.md"
    assert evidence[0].source_url == document.resolve().as_uri()
    assert evidence[0].snippet == (
        "# Market Report Cursor launches features. GitHub Copilot updates docs."
    )
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True


def test_document_reader_limits_snippet_length(tmp_path, monkeypatch) -> None:
    document = tmp_path / "long.md"
    document.write_text("a" * 600, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("long.md", "s1")

    assert len(evidence[0].snippet) == 500


def test_document_reader_rejects_invalid_utf8(tmp_path, monkeypatch) -> None:
    document = tmp_path / "bad.md"
    document.write_bytes(b"\xff\xfe\xfa")
    monkeypatch.chdir(tmp_path)

    assert document_reader("bad.md", "s1") == []


def test_document_reader_rejects_empty_normalized_snippet(tmp_path, monkeypatch) -> None:
    document = tmp_path / "empty.md"
    document.write_text("\n\t   \n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert document_reader("empty.md", "s1") == []


def test_document_reader_uses_relative_path_in_evidence_id(
    tmp_path, monkeypatch
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    first = docs_dir / "Report.md"
    second = docs_dir / "Report.txt"
    first.write_text("First report.", encoding="utf-8")
    second.write_text("Second report.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    first_evidence = document_reader("docs/Report.md", "s1")
    second_evidence = document_reader("docs/Report.txt", "s1")

    assert first_evidence[0].id == document_id_for("docs/Report.md")
    assert second_evidence[0].id == document_id_for("docs/Report.txt")


def test_document_reader_hash_prevents_separator_slug_collisions(
    tmp_path, monkeypatch
) -> None:
    nested_dir = tmp_path / "docs" / "foo"
    nested_dir.mkdir(parents=True)
    first = tmp_path / "docs" / "foo-bar.md"
    second = nested_dir / "bar.md"
    first.write_text("First report.", encoding="utf-8")
    second.write_text("Second report.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    first_evidence = document_reader("docs/foo-bar.md", "s1")
    second_evidence = document_reader("docs/foo/bar.md", "s1")

    assert first_evidence[0].id == document_id_for("docs/foo-bar.md")
    assert second_evidence[0].id == document_id_for("docs/foo/bar.md")
    assert first_evidence[0].id != second_evidence[0].id


@pytest.mark.parametrize(
    "query",
    [
        "missing.md",
        ".",
        "unsupported.pdf",
        "../outside.md",
    ],
)
def test_document_reader_rejects_invalid_paths(query, tmp_path, monkeypatch) -> None:
    (tmp_path / "unsupported.pdf").write_text("pdf text", encoding="utf-8")
    (tmp_path.parent / "outside.md").write_text("outside", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert document_reader(query, "s1") == []


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
    monkeypatch.delenv("INSIGHT_GRAPH_SEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_SEARCH_LIMIT", raising=False)
    monkeypatch.setattr(web_search_module, "pre_fetch_results", fake_pre_fetch_results)

    evidence = ToolRegistry().run("web_search", "Compare AI coding agents", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == "web-search-evidence"
    assert evidence[0].subtask_id == "s1"


def test_registry_runs_github_search_tool() -> None:
    evidence = ToolRegistry().run("github_search", "Compare AI coding agents", "s1")

    assert len(evidence) == 3
    assert evidence[0].id == "github-opencode-repository"
    assert evidence[0].subtask_id == "s1"
    assert all(item.source_type == "github" for item in evidence)


def test_registry_runs_news_search_tool() -> None:
    evidence = ToolRegistry().run("news_search", "AI coding agent funding", "s1")

    assert len(evidence) == 3
    assert evidence[0].id == "news-github-copilot-changelog"
    assert evidence[0].subtask_id == "s1"
    assert {item.source_type for item in evidence} == {"news"}


def test_registry_runs_document_reader_tool(tmp_path, monkeypatch) -> None:
    document = tmp_path / "sample.md"
    document.write_text("Local document evidence.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = ToolRegistry().run("document_reader", "sample.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == document_id_for("sample.md")
    assert evidence[0].source_type == "docs"


def test_registry_unknown_tool_still_raises_key_error() -> None:
    with pytest.raises(KeyError, match="Unknown tool"):
        ToolRegistry().run("missing_tool", "query", "s1")
