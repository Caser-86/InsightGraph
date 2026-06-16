import importlib
import logging

from insight_graph.tools.fetch_url import fetch_url, infer_source_type
from insight_graph.tools.http_client import FetchedPage


def write_minimal_pdf_bytes(text: str) -> bytes:
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
    return bytes(output)


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

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)

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
    assert item.chunk_index == 1


def test_fetch_url_uses_source_type_classifier(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text="""
            <html>
              <head><title>SEC Filing</title></head>
              <body><main><p>SEC filing evidence text.</p></main></body>
            </html>
            """,
        )

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)

    evidence = fetch_url("https://www.sec.gov/Archives/edgar/data/320193/10-k.htm", "s1")

    assert evidence[0].source_type == "sec"


def test_fetch_url_marks_successful_evidence_reachable(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text="""
            <html>
              <head><title>GitHub Repo</title></head>
              <body><main><p>GitHub repository evidence text.</p></main></body>
            </html>
            """,
        )

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)

    evidence = fetch_url("https://github.com/sst/opencode", "s1")

    assert evidence[0].reachable is True
    assert evidence[0].source_trusted is True
    assert evidence[0].claim_supported is None


def test_fetch_url_chunks_long_html_with_section_metadata(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text=(
                "<html><head><title>Long Report</title></head><body><main>"
                "<h1>Executive Summary</h1>"
                + "overview " * 120
                + "<h2>Pricing</h2>"
                + "enterprise pricing " * 80
                + "<h2>Risks</h2>"
                + "risk " * 120
                + "</main></body></html>"
            ),
        )

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)

    evidence = fetch_url("https://example.com/report", "s1")

    assert len(evidence) > 1
    assert [item.chunk_index for item in evidence[:3]] == [1, 2, 3]
    assert evidence[0].id == "example-com-report"
    assert evidence[1].id == "example-com-report-chunk-2"
    assert evidence[0].title == "Long Report"
    assert evidence[1].title == "Long Report (chunk 2)"
    assert evidence[0].section_heading == "Executive Summary"
    assert any(item.section_heading == "Pricing" for item in evidence)
    assert {item.source_url for item in evidence} == {"https://example.com/report"}
    assert {item.verified for item in evidence} == {True}


def test_fetch_url_uses_deeper_chunks_for_deep_plus(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text=(
                "<html><head><title>Very Long Report</title></head><body><main>"
                + "<h1>Market</h1>"
                + "xiaomi auto smartphone aiot smart home delivery revenue " * 500
                + "</main></body></html>"
            ),
        )

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.setenv("INSIGHT_GRAPH_REPORT_INTENSITY", "deep-plus")
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)

    evidence = fetch_url("https://example.com/very-long-report", "s1")

    assert len(evidence) > 5
    assert len(evidence[0].snippet) > 500


def test_fetch_url_ranks_chunks_from_json_query(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        assert url == "https://example.com/report"
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text=(
                "<html><head><title>Long Report</title></head><body><main>"
                + "<h1>Overview</h1>"
                + "pricing " * 90
                + "<h2>Pricing Strategy</h2>"
                + "roadmap details " * 80
                + "</main></body></html>"
            ),
        )

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)

    evidence = fetch_url(
        '{"url":"https://example.com/report","query":"pricing strategy"}',
        "s1",
    )

    assert evidence[0].section_heading == "Pricing Strategy"
    assert "roadmap details" in evidence[0].snippet


def test_fetch_url_uses_rendered_fetch_when_enabled(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        raise AssertionError(f"fetch_text should not be called for rendered fetch: {url}")

    def fake_render_page(url: str):
        assert url == "https://example.com/app"
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text="""
            <html>
              <head><title>Rendered App</title></head>
              <body><main><p>Client rendered evidence text.</p></main></body>
            </html>
            """,
        )

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.setenv("INSIGHT_GRAPH_FETCH_RENDERED", "1")
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)
    monkeypatch.setattr(fetch_url_module, "render_page", fake_render_page, raising=False)

    evidence = fetch_url("https://example.com/app", "s1")

    assert len(evidence) == 1
    assert evidence[0].title == "Rendered App"
    assert evidence[0].snippet == "Client rendered evidence text."


def test_fetch_url_reads_remote_pdf_with_page_metadata(monkeypatch) -> None:
    pdf_bytes = write_minimal_pdf_bytes("Remote PDF evidence text.")

    def fake_fetch_text(url: str):
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="application/pdf",
            text=pdf_bytes.decode("latin-1"),
            body=pdf_bytes,
        )

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)

    evidence = fetch_url("https://example.com/report.pdf", "s1")

    assert len(evidence) == 1
    item = evidence[0]
    assert item.id == "example-com-report-pdf"
    assert item.title == "report.pdf"
    assert item.source_url == "https://example.com/report.pdf"
    assert item.snippet == "Remote PDF evidence text."
    assert item.source_type == "docs"
    assert item.verified is True
    assert item.chunk_index == 1
    assert item.document_page == 1


def test_fetch_url_uses_configured_cache_for_pdf_bytes(tmp_path, monkeypatch) -> None:
    pdf_bytes = write_minimal_pdf_bytes("Cached remote PDF evidence text.")
    calls = 0

    def fake_fetch_text(url: str):
        nonlocal calls
        calls += 1
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="application/pdf",
            text=pdf_bytes.decode("latin-1"),
            body=pdf_bytes,
        )

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.setenv("INSIGHT_GRAPH_FETCH_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)

    first = fetch_url("https://example.com/report.pdf?utm_source=newsletter", "s1")
    second = fetch_url("https://example.com/report.pdf", "s1")

    assert calls == 1
    assert first[0].snippet == "Cached remote PDF evidence text."
    assert second[0].snippet == "Cached remote PDF evidence text."


def test_fetch_url_does_not_cache_when_cache_dir_is_unset(monkeypatch) -> None:
    pdf_bytes = write_minimal_pdf_bytes("Uncached remote PDF evidence text.")
    calls = 0

    def fake_fetch_text(url: str):
        nonlocal calls
        calls += 1
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="application/pdf",
            text=pdf_bytes.decode("latin-1"),
            body=pdf_bytes,
        )

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.delenv("INSIGHT_GRAPH_FETCH_CACHE_DIR", raising=False)
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)

    fetch_url("https://example.com/report.pdf", "s1")
    fetch_url("https://example.com/report.pdf", "s1")

    assert calls == 2


def test_fetch_url_suppresses_pypdf_logger_during_remote_pdf_parse(monkeypatch) -> None:
    class FakePdfPage:
        def extract_text(self) -> str:
            return "Quiet PDF evidence text."

    class RecordingPdfReader:
        is_encrypted = False
        pages = [FakePdfPage()]

        def __init__(self, stream) -> None:
            del stream
            assert logging.getLogger("pypdf").level == logging.CRITICAL + 1

    def fake_fetch_text(url: str):
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="application/pdf",
            text="",
            body=b"%PDF-1.4",
        )

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    previous_level = logging.getLogger("pypdf").level
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)
    monkeypatch.setattr(fetch_url_module, "PdfReader", RecordingPdfReader)

    evidence = fetch_url("https://example.com/report.pdf", "s1")

    assert evidence[0].snippet == "Quiet PDF evidence text."
    assert logging.getLogger("pypdf").level == previous_level


def test_fetch_url_returns_empty_list_for_empty_snippet(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        return FetchedPage(url=url, status_code=200, content_type="text/html", text="<html></html>")

    fetch_url_module = importlib.import_module("insight_graph.tools.fetch_url")
    monkeypatch.setattr(fetch_url_module, "fetch_text", fake_fetch_text)

    assert fetch_url("https://example.com/empty", "s1") == []


def test_infer_source_type_from_url() -> None:
    assert infer_source_type("https://github.com/sst/opencode") == "github"
    assert infer_source_type("https://docs.github.com/copilot") == "docs"
    assert infer_source_type("https://example.com/docs/product") == "docs"
    assert infer_source_type("https://example.com/report.pdf") == "docs"
    assert infer_source_type("https://www.sec.gov/Archives/edgar/data/320193/10-k.htm") == "sec"
    assert infer_source_type("https://www.reuters.com/technology/ai-agents") == "news"
    assert infer_source_type("https://blog.example.com/post") == "blog"
    assert infer_source_type("https://arxiv.org/abs/2401.12345") == "paper"
    assert infer_source_type("https://example.com/product") == "unknown"
