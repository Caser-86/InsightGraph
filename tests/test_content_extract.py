from insight_graph.tools.content_extract import extract_page_content


def test_extract_page_content_returns_title_text_and_snippet() -> None:
    html = """
    <html>
      <head><title>Example Product Page</title></head>
      <body>
        <main>
          <h1>Product Overview</h1>
          <p>Cursor helps developers write code with AI assistance.</p>
          <p>It supports editing, chat, and codebase-aware workflows.</p>
        </main>
      </body>
    </html>
    """

    content = extract_page_content(html, "https://example.com/product", snippet_chars=80)

    assert content.title == "Example Product Page"
    assert "Product Overview" in content.text
    assert "Cursor helps developers" in content.text
    assert len(content.snippet) <= 80
    assert content.snippet.startswith("Product Overview")


def test_extract_page_content_removes_non_content_tags() -> None:
    html = """
    <html>
      <head><title>Noise Removal</title><style>.hidden { display: none; }</style></head>
      <body>
        <nav>Navigation should not appear</nav>
        <script>window.secret = "do not include";</script>
        <main><p>Only this useful evidence should remain.</p></main>
        <footer>Footer should not appear</footer>
      </body>
    </html>
    """

    content = extract_page_content(html, "https://example.com/noise")

    assert "Only this useful evidence should remain." in content.text
    assert "Navigation should not appear" not in content.text
    assert "do not include" not in content.text
    assert "Footer should not appear" not in content.text


def test_extract_page_content_falls_back_to_domain_for_missing_title() -> None:
    html = "<html><body><main><p>Useful body text.</p></main></body></html>"

    content = extract_page_content(html, "https://docs.example.com/path")

    assert content.title == "docs.example.com"
    assert content.text == "Useful body text."
    assert content.snippet == "Useful body text."
