from insight_graph.state import Evidence
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.web_search import SearchResult


def pre_fetch_results(
    results: list[SearchResult],
    subtask_id: str = "collect",
    limit: int = 3,
) -> list[Evidence]:
    evidence: list[Evidence] = []
    for result in results[:limit]:
        evidence.extend(fetch_url(result.url, subtask_id))
    return evidence
