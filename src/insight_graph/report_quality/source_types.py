from urllib.parse import urlparse

from insight_graph.state import SourceType

NEWS_DOMAINS = {
    "apnews.com",
    "bloomberg.com",
    "cnbc.com",
    "ft.com",
    "reuters.com",
    "techcrunch.com",
    "theverge.com",
    "wsj.com",
}


def infer_source_type(url: str) -> SourceType:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    if _is_sec_source(domain, path):
        return "sec"
    if _is_paper_source(domain, path):
        return "paper"
    if (
        domain.startswith("docs.")
        or "/docs" in path
        or "/documentation" in path
        or path.endswith(".pdf")
    ):
        return "docs"
    if domain == "github.com" or domain.endswith(".github.com"):
        return "github"
    if _is_news_domain(domain):
        return "news"
    if domain.startswith("blog.") or "/blog" in path or "/posts" in path:
        return "blog"
    return "unknown"


def _is_sec_source(domain: str, path: str) -> bool:
    return domain.endswith("sec.gov") or "/edgar/" in path or "/archives/edgar/" in path


def _is_paper_source(domain: str, path: str) -> bool:
    return domain == "arxiv.org" or domain.endswith("semanticscholar.org") or "/paper" in path


def _is_news_domain(domain: str) -> bool:
    return any(
        domain == news_domain or domain.endswith(f".{news_domain}")
        for news_domain in NEWS_DOMAINS
    )
