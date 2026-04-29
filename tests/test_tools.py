import hashlib
import importlib
import json
import re

import pytest
from pypdf import PdfWriter

from insight_graph.state import Evidence
from insight_graph.tools import (
    SearchResult,
    ToolRegistry,
    document_reader,
    fetch_url,
    github_search,
    list_directory,
    news_search,
    read_file,
    sec_filings,
    web_search,
    write_file,
)
from insight_graph.tools.http_client import FetchedPage


def tool_id(prefix: str, relative_path: str, slug_input: str | None = None) -> str:
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:8]
    value = slug_input if slug_input is not None else relative_path
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "root"
    return f"{prefix}-{slug}-{digest}"


def document_id_for(relative_path: str) -> str:
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", relative_path.lower()).strip("-")
    return f"document-{slug or 'document'}-{digest}"


def write_minimal_pdf(path, text: str) -> None:
    escaped_text = text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")
    content = f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content.encode('utf-8'))} >>\nstream\n{content}\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n{body}\nendobj\n".encode())
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    path.write_bytes(bytes(output))


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


def test_tools_package_exports_sec_filings_callable() -> None:
    assert callable(sec_filings)


def test_tools_package_exports_document_reader_callable() -> None:
    assert callable(document_reader)


def test_tools_package_exports_readonly_file_tool_callables() -> None:
    assert callable(read_file)
    assert callable(list_directory)
    assert callable(write_file)


def test_github_search_returns_deterministic_verified_github_evidence(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_GITHUB_PROVIDER", raising=False)

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


def test_github_search_live_provider_maps_repository_results(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_fetch_json(url: str, headers: dict[str, str], timeout: float):
        observed["url"] = url
        observed["headers"] = headers
        observed["timeout"] = timeout
        return {
            "items": [
                {
                    "full_name": "example/insightgraph",
                    "html_url": "https://github.com/example/insightgraph",
                    "description": "Research graph for competitive intelligence.",
                    "stargazers_count": 42,
                    "language": "Python",
                    "updated_at": "2026-04-26T12:00:00Z",
                }
            ]
        }

    github_search_module = importlib.import_module("insight_graph.tools.github_search")
    monkeypatch.setenv("INSIGHT_GRAPH_GITHUB_PROVIDER", "live")
    monkeypatch.setenv("INSIGHT_GRAPH_GITHUB_LIMIT", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(github_search_module, "fetch_github_json", fake_fetch_json)

    evidence = github_search("InsightGraph competitive intelligence", "s1")

    assert observed["url"] == (
        "https://api.github.com/search/repositories?"
        "q=InsightGraph+competitive+intelligence&per_page=1"
    )
    assert observed["headers"] == {
        "Accept": "application/vnd.github+json",
        "User-Agent": "InsightGraph/0.1",
        "Authorization": "Bearer test-token",
    }
    assert observed["timeout"] == 10.0
    assert len(evidence) == 1
    assert evidence[0].id == "github-example-insightgraph"
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "example/insightgraph"
    assert evidence[0].source_url == "https://github.com/example/insightgraph"
    assert evidence[0].snippet == (
        "Research graph for competitive intelligence. Stars: 42. "
        "Language: Python. Updated: 2026-04-26T12:00:00Z."
    )
    assert evidence[0].source_type == "github"
    assert evidence[0].verified is True


def test_github_search_live_provider_allows_anonymous_requests(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_fetch_json(url: str, headers: dict[str, str], timeout: float):
        observed["headers"] = headers
        return {"items": []}

    github_search_module = importlib.import_module("insight_graph.tools.github_search")
    monkeypatch.setenv("INSIGHT_GRAPH_GITHUB_PROVIDER", "live")
    monkeypatch.delenv("INSIGHT_GRAPH_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(github_search_module, "fetch_github_json", fake_fetch_json)

    assert github_search("InsightGraph", "s1") == []
    assert "Authorization" not in observed["headers"]


def test_github_search_live_provider_returns_empty_on_fetch_error(monkeypatch) -> None:
    def fake_fetch_json(url: str, headers: dict[str, str], timeout: float):
        raise RuntimeError("HTTP error while fetching GitHub API: 403")

    github_search_module = importlib.import_module("insight_graph.tools.github_search")
    monkeypatch.setenv("INSIGHT_GRAPH_GITHUB_PROVIDER", "live")
    monkeypatch.setattr(github_search_module, "fetch_github_json", fake_fetch_json)

    assert github_search("InsightGraph", "s1") == []


def test_github_search_live_provider_returns_empty_on_unexpected_json_shape(
    monkeypatch,
) -> None:
    def fake_fetch_json(url: str, headers: dict[str, str], timeout: float):
        return []

    github_search_module = importlib.import_module("insight_graph.tools.github_search")
    monkeypatch.setenv("INSIGHT_GRAPH_GITHUB_PROVIDER", "live")
    monkeypatch.setattr(github_search_module, "fetch_github_json", fake_fetch_json)

    assert github_search("InsightGraph", "s1") == []


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


def test_sec_filings_maps_recent_company_filings(monkeypatch) -> None:
    sec_module = importlib.import_module("insight_graph.tools.sec_filings")
    observed: dict[str, object] = {}

    def fake_fetch_json(url: str, headers: dict[str, str], timeout: float):
        observed["url"] = url
        observed["headers"] = headers
        observed["timeout"] = timeout
        return {
            "filings": {
                "recent": {
                    "form": ["10-K", "10-Q", "8-K"],
                    "accessionNumber": [
                        "0000320193-23-000106",
                        "0000320193-23-000077",
                        "0000320193-23-000064",
                    ],
                    "filingDate": ["2023-11-03", "2023-08-04", "2023-05-05"],
                    "primaryDocument": ["aapl-20230930.htm", "aapl-20230701.htm", "aapl.htm"],
                }
            }
        }

    monkeypatch.setattr(sec_module, "fetch_sec_json", fake_fetch_json)

    evidence = sec_filings("AAPL", "s1")

    assert len(evidence) == 3
    assert evidence[0].id == "sec-aapl-10-k-2023-11-03"
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "AAPL 10-K filing 2023-11-03"
    assert evidence[0].source_url == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019323000106/aapl-20230930.htm"
    )
    assert evidence[0].source_type == "official_site"
    assert evidence[0].verified is True
    assert "AAPL filed 10-K on 2023-11-03." in evidence[0].snippet
    assert observed["url"] == "https://data.sec.gov/submissions/CIK0000320193.json"
    assert observed["timeout"] == 10.0
    assert observed["headers"]["User-Agent"] == "InsightGraph contact@example.com"


def test_sec_filings_accepts_company_name_alias(monkeypatch) -> None:
    sec_module = importlib.import_module("insight_graph.tools.sec_filings")
    observed: dict[str, object] = {}

    def fake_fetch_json(url: str, headers: dict[str, str], timeout: float):
        observed["url"] = url
        return {
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "accessionNumber": ["0000320193-23-000106"],
                    "filingDate": ["2023-11-03"],
                    "primaryDocument": ["aapl-20230930.htm"],
                }
            }
        }

    monkeypatch.setattr(sec_module, "fetch_sec_json", fake_fetch_json)

    evidence = sec_filings("Analyze Apple filings and competitive risks", "s1")

    assert [item.id for item in evidence] == ["sec-aapl-10-k-2023-11-03"]
    assert observed["url"] == "https://data.sec.gov/submissions/CIK0000320193.json"


def test_sec_filings_returns_empty_for_unknown_ticker() -> None:
    assert sec_filings("not-a-known-ticker", "s1") == []


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
    assert evidence[0].chunk_index == 1
    assert evidence[0].section_heading == "Market Report"


def test_document_reader_reads_html_visible_text(tmp_path, monkeypatch) -> None:
    document = tmp_path / "market.html"
    document.write_text(
        """
        <!doctype html>
        <html>
          <head>
            <title>Ignored page title</title>
            <style>.hidden { display: none; }</style>
            <script>window.secret = "do not include";</script>
          </head>
          <body>
            <h1>Market Brief</h1>
            <p>Cursor adds agent mode.</p>
            <noscript>Do not include noscript fallback.</noscript>
            <p>GitHub Copilot updates docs.</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("market.html", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == document_id_for("market.html")
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "market.html"
    assert evidence[0].source_url == document.resolve().as_uri()
    assert evidence[0].snippet == (
        "Market Brief Cursor adds agent mode. GitHub Copilot updates docs."
    )
    assert "ignored page title" not in evidence[0].snippet.lower()
    assert "do not include" not in evidence[0].snippet.lower()
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True


def test_document_reader_accepts_htm_suffix(tmp_path, monkeypatch) -> None:
    document = tmp_path / "brief.htm"
    document.write_text(
        "<html><body><main><p>Local HTM research note.</p></main></body></html>",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("brief.htm", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == document_id_for("brief.htm")
    assert evidence[0].title == "brief.htm"
    assert evidence[0].snippet == "Local HTM research note."


def test_document_reader_reads_pdf_text(tmp_path, monkeypatch) -> None:
    document = tmp_path / "market.pdf"
    write_minimal_pdf(document, "PDF market brief for Cursor and GitHub Copilot.")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("market.pdf", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == document_id_for("market.pdf")
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "market.pdf"
    assert evidence[0].source_url == document.resolve().as_uri()
    assert evidence[0].snippet == "PDF market brief for Cursor and GitHub Copilot."
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True
    assert evidence[0].chunk_index == 1
    assert evidence[0].document_page == 1


def test_document_reader_rejects_malformed_pdf_without_parser_output(
    tmp_path, monkeypatch, capsys, caplog
) -> None:
    caplog.set_level("WARNING")
    document = tmp_path / "broken.pdf"
    document.write_bytes(b"not a valid pdf")
    monkeypatch.chdir(tmp_path)

    assert document_reader("broken.pdf", "s1") == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert caplog.text == ""


def test_document_reader_rejects_pdf_without_extractable_text(tmp_path, monkeypatch) -> None:
    document = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with document.open("wb") as handle:
        writer.write(handle)
    monkeypatch.chdir(tmp_path)

    assert document_reader("blank.pdf", "s1") == []


def test_document_reader_rejects_encrypted_pdf(tmp_path, monkeypatch) -> None:
    document = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret")
    with document.open("wb") as handle:
        writer.write(handle)
    monkeypatch.chdir(tmp_path)

    assert document_reader("encrypted.pdf", "s1") == []


def test_document_reader_limits_snippet_length(tmp_path, monkeypatch) -> None:
    document = tmp_path / "long.md"
    document.write_text("a" * 600, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("long.md", "s1")

    assert len(evidence[0].snippet) == 500


def test_document_reader_keeps_exact_limit_document_as_single_evidence(
    tmp_path, monkeypatch
) -> None:
    document = tmp_path / "exact.md"
    document.write_text("a" * 500, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("exact.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == document_id_for("exact.md")
    assert evidence[0].title == "exact.md"
    assert len(evidence[0].snippet) == 500


def test_document_reader_chunks_long_documents(tmp_path, monkeypatch) -> None:
    document = tmp_path / "long.md"
    text = "".join(str(index % 10) for index in range(2200))
    document.write_text(text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("long.md", "s1")

    assert len(evidence) == 5
    assert [len(item.snippet) for item in evidence] == [500, 500, 500, 500, 500]
    assert evidence[0].id == document_id_for("long.md")
    assert evidence[1].id == f"{document_id_for('long.md')}-chunk-2"
    assert evidence[4].id == f"{document_id_for('long.md')}-chunk-5"
    assert evidence[0].title == "long.md"
    assert evidence[1].title == "long.md (chunk 2)"
    assert evidence[4].title == "long.md (chunk 5)"
    assert [item.chunk_index for item in evidence] == [1, 2, 3, 4, 5]
    assert evidence[0].snippet[-100:] == evidence[1].snippet[:100]
    assert {item.source_url for item in evidence} == {document.resolve().as_uri()}
    assert {item.source_type for item in evidence} == {"docs"}
    assert {item.verified for item in evidence} == {True}


def test_document_reader_ranks_chunks_with_json_query(tmp_path, monkeypatch) -> None:
    document = tmp_path / "ranked.md"
    chunks = [
        "alpha " * 100,
        "beta " * 100,
        "enterprise pricing " * 40,
        "gamma " * 100,
    ]
    document.write_text(" ".join(chunks), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader(
        '{"path":"ranked.md","query":"enterprise pricing"}',
        "s1",
    )

    assert len(evidence) >= 1
    assert "enterprise pricing" in evidence[0].snippet
    assert evidence[0].id.endswith("chunk-3") or evidence[0].id.endswith("chunk-4")
    assert evidence[0].title.startswith("ranked.md (chunk ")
    assert evidence[0].source_url == document.resolve().as_uri()
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True
    assert evidence[0].chunk_index in {3, 4}


def test_document_reader_records_section_heading_for_ranked_markdown(
    tmp_path, monkeypatch
) -> None:
    document = tmp_path / "sections.md"
    document.write_text(
        "# Executive Summary\n"
        + "overview " * 120
        + "\n## Pricing\n"
        + "enterprise pricing " * 40
        + "\n## Risks\n"
        + "risk " * 120,
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    evidence = document_reader(
        '{"path":"sections.md","query":"enterprise pricing"}',
        "s1",
    )

    assert evidence[0].section_heading == "Pricing"
    assert evidence[0].chunk_index >= 1


def test_document_reader_json_query_falls_back_when_no_terms_match(
    tmp_path, monkeypatch
) -> None:
    document = tmp_path / "fallback.md"
    document.write_text("alpha " * 500, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader('{"path":"fallback.md","query":"unmatched"}', "s1")

    assert len(evidence) == 5
    assert evidence[0].id == document_id_for("fallback.md")
    assert evidence[1].id == f"{document_id_for('fallback.md')}-chunk-2"


def test_document_reader_invalid_json_input_is_treated_as_path(
    tmp_path, monkeypatch
) -> None:
    document = tmp_path / "{not-json}.md"
    document.write_text("Curly filename content.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("{not-json}.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].title == "{not-json}.md"
    assert evidence[0].snippet == "Curly filename content."


def test_document_reader_json_object_without_valid_path_returns_empty() -> None:
    assert document_reader('{"query":"pricing"}', "s1") == []
    assert document_reader('{"path":"","query":"pricing"}', "s1") == []
    assert document_reader('{"path":123,"query":"pricing"}', "s1") == []


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
        "unsupported.docx",
        "../outside.md",
    ],
)
def test_document_reader_rejects_invalid_paths(query, tmp_path, monkeypatch) -> None:
    (tmp_path / "unsupported.docx").write_text("docx text", encoding="utf-8")
    (tmp_path.parent / "outside.md").write_text("outside", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert document_reader(query, "s1") == []


def test_read_file_returns_verified_docs_evidence(tmp_path, monkeypatch) -> None:
    document = tmp_path / "docs" / "Notes.md"
    document.parent.mkdir()
    document.write_text("# Notes\n\nAlpha   beta.\nGamma", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = read_file("docs/Notes.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == tool_id("read-file", "docs/Notes.md")
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "Notes.md"
    assert evidence[0].source_url == document.resolve().as_uri()
    assert evidence[0].snippet == "# Notes Alpha beta. Gamma"
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True


def test_read_file_rejects_unsafe_or_invalid_files(tmp_path, monkeypatch) -> None:
    (tmp_path / "unsupported.bin").write_bytes(b"data")
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe\xfa")
    (tmp_path / "empty.md").write_text("\n\t   \n", encoding="utf-8")
    (tmp_path / "large.md").write_text("a" * (64 * 1024 + 1), encoding="utf-8")
    (tmp_path.parent / "outside.md").write_text("outside", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert read_file("missing.md", "s1") == []
    assert read_file(".", "s1") == []
    assert read_file("unsupported.bin", "s1") == []
    assert read_file("bad.md", "s1") == []
    assert read_file("empty.md", "s1") == []
    assert read_file("large.md", "s1") == []
    assert read_file("../outside.md", "s1") == []


def test_read_file_rejects_malformed_query(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert read_file(None, "s1") == []  # type: ignore[arg-type]


def test_read_file_hash_prevents_slug_collisions(tmp_path, monkeypatch) -> None:
    nested_dir = tmp_path / "docs" / "foo"
    nested_dir.mkdir(parents=True)
    first = tmp_path / "docs" / "foo-bar.md"
    second = nested_dir / "bar.md"
    first.write_text("First.", encoding="utf-8")
    second.write_text("Second.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    first_evidence = read_file("docs/foo-bar.md", "s1")
    second_evidence = read_file("docs/foo/bar.md", "s1")

    assert first_evidence[0].id == tool_id("read-file", "docs/foo-bar.md")
    assert second_evidence[0].id == tool_id("read-file", "docs/foo/bar.md")
    assert first_evidence[0].id != second_evidence[0].id


def test_list_directory_returns_one_level_listing(tmp_path, monkeypatch) -> None:
    target = tmp_path / "docs"
    target.mkdir()
    (target / "b.md").write_text("b", encoding="utf-8")
    (target / "A.txt").write_text("a", encoding="utf-8")
    (target / "nested").mkdir()
    monkeypatch.chdir(tmp_path)

    evidence = list_directory("docs", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == tool_id("list-directory", "docs")
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "Directory listing: docs"
    assert evidence[0].source_url == target.resolve().as_uri()
    assert evidence[0].snippet == "A.txt\nb.md\nnested/"
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True


def test_list_directory_handles_root_and_empty_directory(tmp_path, monkeypatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(tmp_path)

    root_evidence = list_directory(".", "s1")
    empty_evidence = list_directory("empty", "s1")

    assert root_evidence[0].id == tool_id("list-directory", ".", "root")
    assert root_evidence[0].title == "Directory listing: ."
    assert empty_evidence[0].snippet == "(empty directory)"


def test_list_directory_handles_empty_string_as_root(tmp_path, monkeypatch) -> None:
    (tmp_path / "sample.md").write_text("sample", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = list_directory("", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == tool_id("list-directory", ".", "root")
    assert evidence[0].title == "Directory listing: ."
    assert "sample.md" in evidence[0].snippet


def test_list_directory_rejects_malformed_query(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert list_directory(None, "s1") == []  # type: ignore[arg-type]


def test_list_directory_limits_entries_and_snippet_length(tmp_path, monkeypatch) -> None:
    for index in range(60):
        (tmp_path / f"e{index:02d}.md").write_text("sample", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = list_directory(".", "s1")

    entries = evidence[0].snippet.split("\n")
    assert len(entries) == 50
    assert entries[0] == "e00.md"
    assert entries[-1] == "e49.md"
    assert "e50.md" not in entries
    assert len(evidence[0].snippet) <= 500


def test_list_directory_does_not_follow_outside_directory_symlink(
    tmp_path, monkeypatch
) -> None:
    outside = tmp_path.parent / "outside-dir"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "outside-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are not supported in this environment")
    monkeypatch.chdir(tmp_path)

    evidence = list_directory(".", "s1")

    assert "outside-link" in evidence[0].snippet.split("\n")
    assert "outside-link/" not in evidence[0].snippet.split("\n")


def test_list_directory_rejects_invalid_paths(tmp_path, monkeypatch) -> None:
    (tmp_path / "file.md").write_text("file", encoding="utf-8")
    (tmp_path.parent / "outside").mkdir(exist_ok=True)
    monkeypatch.chdir(tmp_path)

    assert list_directory("missing", "s1") == []
    assert list_directory("file.md", "s1") == []
    assert list_directory("../outside", "s1") == []


def test_write_file_creates_verified_docs_evidence(tmp_path, monkeypatch) -> None:
    target_dir = tmp_path / "notes"
    target_dir.mkdir()
    target = target_dir / "Output.md"
    monkeypatch.chdir(tmp_path)

    evidence = write_file(
        json.dumps({"path": "notes/Output.md", "content": "# Output\n\nAlpha   beta."}),
        "s1",
    )

    assert target.read_text(encoding="utf-8") == "# Output\n\nAlpha   beta."
    assert len(evidence) == 1
    assert evidence[0].id == tool_id("write-file", "notes/Output.md")
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "Output.md"
    assert evidence[0].source_url == target.resolve().as_uri()
    assert evidence[0].snippet == "# Output Alpha beta."
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True


def test_write_file_normalizes_newlines_to_lf(tmp_path, monkeypatch) -> None:
    target = tmp_path / "notes.md"
    monkeypatch.chdir(tmp_path)

    evidence = write_file(
        json.dumps({"path": "notes.md", "content": "Line 1\r\nLine 2"}),
        "s1",
    )

    assert len(evidence) == 1
    assert target.read_bytes() == b"Line 1\nLine 2"


@pytest.mark.parametrize(
    "query",
    [
        "not-json",
        json.dumps(["path", "content"]),
        json.dumps({"content": "Missing path."}),
        json.dumps({"path": "missing-content.md"}),
        json.dumps({"path": 123, "content": "Bad path."}),
        json.dumps({"path": "bad-content.md", "content": 123}),
        json.dumps({"path": "overwrite.md", "content": "x", "overwrite": True}),
        json.dumps({"path": "append.md", "content": "x", "append": True}),
        json.dumps({"path": "mode.md", "content": "x", "mode": "overwrite"}),
    ],
)
def test_write_file_rejects_invalid_query_shapes(query, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert write_file(query, "s1") == []


def test_write_file_rejects_unsafe_or_invalid_targets(tmp_path, monkeypatch) -> None:
    existing = tmp_path / "existing.md"
    existing.write_text("existing", encoding="utf-8")
    (tmp_path / "folder").mkdir()
    (tmp_path.parent / "outside.md").write_text("outside", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert write_file(json.dumps({"path": "existing.md", "content": "new"}), "s1") == []
    assert existing.read_text(encoding="utf-8") == "existing"
    assert write_file(json.dumps({"path": "folder", "content": "new"}), "s1") == []
    assert write_file(json.dumps({"path": "missing/out.md", "content": "new"}), "s1") == []
    assert write_file(json.dumps({"path": "../outside.md", "content": "new"}), "s1") == []
    assert write_file(json.dumps({"path": "unsupported.pdf", "content": "new"}), "s1") == []
    assert write_file(json.dumps({"path": "script.py", "content": "print('no')"}), "s1") == []
    assert write_file(json.dumps({"path": "empty.md", "content": "\n\t   \n"}), "s1") == []
    assert write_file(
        json.dumps({"path": "large.md", "content": "a" * (64 * 1024 + 1)}), "s1"
    ) == []


def test_write_file_rejects_colon_path_components(tmp_path, monkeypatch) -> None:
    existing = tmp_path / "existing.md"
    existing.write_text("existing", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert write_file(
        json.dumps({"path": "existing.md:stream.md", "content": "hidden"}), "s1"
    ) == []
    assert existing.read_text(encoding="utf-8") == "existing"


def test_write_file_rejects_malformed_query(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert write_file(None, "s1") == []  # type: ignore[arg-type]


def test_write_file_rejects_binary_like_content(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert write_file(json.dumps({"path": "binary.md", "content": "alpha\x00beta"}), "s1") == []
    assert not (tmp_path / "binary.md").exists()


def test_write_file_rejects_deeply_nested_json(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    query = "[" * 20000 + "]" * 20000

    assert write_file(query, "s1") == []


def test_write_file_hash_prevents_slug_collisions(tmp_path, monkeypatch) -> None:
    nested_dir = tmp_path / "docs" / "foo"
    nested_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    first_evidence = write_file(json.dumps({"path": "docs/foo-bar.md", "content": "First."}), "s1")
    second_evidence = write_file(
        json.dumps({"path": "docs/foo/bar.md", "content": "Second."}), "s1"
    )

    assert first_evidence[0].id == tool_id("write-file", "docs/foo-bar.md")
    assert second_evidence[0].id == tool_id("write-file", "docs/foo/bar.md")
    assert first_evidence[0].id != second_evidence[0].id


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


def test_registry_runs_github_search_tool(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_GITHUB_PROVIDER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_GITHUB_LIMIT", raising=False)

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


def test_registry_runs_sec_filings_tool(monkeypatch) -> None:
    sec_module = importlib.import_module("insight_graph.tools.sec_filings")

    def fake_fetch_json(url: str, headers: dict[str, str], timeout: float):
        return {
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "accessionNumber": ["0000320193-23-000106"],
                    "filingDate": ["2023-11-03"],
                    "primaryDocument": ["aapl-20230930.htm"],
                }
            }
        }

    monkeypatch.setattr(sec_module, "fetch_sec_json", fake_fetch_json)

    evidence = ToolRegistry().run("sec_filings", "AAPL", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == "sec-aapl-10-k-2023-11-03"


def test_registry_runs_document_reader_tool(tmp_path, monkeypatch) -> None:
    document = tmp_path / "sample.md"
    document.write_text("Local document evidence.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = ToolRegistry().run("document_reader", "sample.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == document_id_for("sample.md")
    assert evidence[0].source_type == "docs"


def test_registry_runs_read_file_tool(tmp_path, monkeypatch) -> None:
    document = tmp_path / "sample.md"
    document.write_text("Local file evidence.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = ToolRegistry().run("read_file", "sample.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == tool_id("read-file", "sample.md")
    assert evidence[0].source_type == "docs"


def test_registry_runs_list_directory_tool(tmp_path, monkeypatch) -> None:
    (tmp_path / "sample.md").write_text("Local file evidence.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = ToolRegistry().run("list_directory", ".", "s1")

    assert len(evidence) == 1
    assert "sample.md" in evidence[0].snippet
    assert evidence[0].source_type == "docs"


def test_registry_runs_write_file_tool(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    evidence = ToolRegistry().run(
        "write_file",
        json.dumps({"path": "sample.md", "content": "Local file evidence."}),
        "s1",
    )

    assert len(evidence) == 1
    assert evidence[0].id == tool_id("write-file", "sample.md")
    assert evidence[0].source_type == "docs"
    assert (tmp_path / "sample.md").read_text(encoding="utf-8") == "Local file evidence."


def test_registry_unknown_tool_still_raises_key_error() -> None:
    with pytest.raises(KeyError, match="Unknown tool"):
        ToolRegistry().run("missing_tool", "query", "s1")
