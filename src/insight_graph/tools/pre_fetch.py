import json

from insight_graph.report_quality.budgeting import get_research_budgets
from insight_graph.state import Evidence
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.search_providers import SearchResult


def pre_fetch_results(
    results: list[SearchResult],
    subtask_id: str = "collect",
    limit: int = 3,
    query: str | None = None,
) -> list[Evidence]:
    evidence: list[Evidence] = []
    fetch_limit = min(limit, get_research_budgets().max_fetches)
    for result in results[:fetch_limit]:
        try:
            evidence.extend(fetch_url(_fetch_query(result.url, query), subtask_id))
        except Exception:
            continue
    return evidence


def _fetch_query(url: str, query: str | None) -> str:
    if not query:
        return url
    return json.dumps({"url": url, "query": query}, separators=(",", ":"))
