from insight_graph.report_quality.source_types import infer_source_type


def test_infer_source_type_detects_sec_sources() -> None:
    assert infer_source_type("https://www.sec.gov/Archives/edgar/data/320193/10-k.htm") == "sec"
    assert infer_source_type("https://data.sec.gov/submissions/CIK0000320193.json") == "sec"


def test_infer_source_type_detects_news_and_blog_sources() -> None:
    assert infer_source_type("https://www.reuters.com/technology/ai-agents") == "news"
    assert infer_source_type("https://blog.example.com/product-launch") == "blog"
    assert infer_source_type("https://example.com/blog/product-launch") == "blog"


def test_infer_source_type_detects_docs_github_and_papers() -> None:
    assert infer_source_type("https://docs.github.com/copilot") == "docs"
    assert infer_source_type("https://github.com/sst/opencode") == "github"
    assert infer_source_type("https://arxiv.org/abs/2401.12345") == "paper"
    assert infer_source_type("https://example.com/report.pdf") == "docs"
