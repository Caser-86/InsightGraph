from insight_graph.state import Evidence
from insight_graph.tools.pre_fetch import pre_fetch_results
from insight_graph.tools.search_providers import (
    parse_search_limit,
    resolve_search_providers,
    search_news_with_providers,
)


def news_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    limit = parse_search_limit()
    if resolve_search_providers() == ["mock"]:
        return _mock_news_evidence(subtask_id)

    news_query = _news_query(query)
    results = search_news_with_providers(news_query, limit)
    evidence = pre_fetch_results(results, subtask_id, limit=limit, query=news_query)
    return [_as_news_evidence(item) for item in evidence]


def _news_query(query: str) -> str:
    recency_hint = "latest recent news 2024 2025 2026"
    return f"{query.strip()} {recency_hint}".strip()


def _as_news_evidence(evidence: Evidence) -> Evidence:
    return evidence.model_copy(update={"source_type": "news"})


def _mock_news_evidence(subtask_id: str) -> list[Evidence]:
    return [
        Evidence(
            id="news-github-copilot-changelog",
            subtask_id=subtask_id,
            title="GitHub Copilot Product Changelog",
            source_url="https://github.blog/changelog/",
            snippet=(
                "GitHub's changelog publishes product updates and release notes for "
                "GitHub Copilot and adjacent developer platform features."
            ),
            source_type="news",
            verified=True,
        ),
        Evidence(
            id="news-openai-codex-update",
            subtask_id=subtask_id,
            title="OpenAI Codex Product Update",
            source_url="https://openai.com/index/introducing-codex/",
            snippet=(
                "OpenAI's Codex announcement describes product capabilities and release "
                "context for cloud-based coding assistance."
            ),
            source_type="news",
            verified=True,
        ),
        Evidence(
            id="news-cursor-changelog",
            subtask_id=subtask_id,
            title="Cursor Product Changelog",
            source_url="https://www.cursor.com/changelog",
            snippet=(
                "Cursor's changelog tracks product updates, feature launches, and release "
                "signals for the AI coding editor."
            ),
            source_type="news",
            verified=True,
        ),
    ]
