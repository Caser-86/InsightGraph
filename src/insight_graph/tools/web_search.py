from pydantic import BaseModel

from insight_graph.state import Evidence


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "mock"


from insight_graph.tools.pre_fetch import pre_fetch_results  # noqa: E402


def mock_web_search(query: str) -> list[SearchResult]:
    return [
        SearchResult(
            title="Cursor Pricing",
            url="https://cursor.com/pricing",
            snippet="Cursor pricing information for AI coding plans.",
        ),
        SearchResult(
            title="GitHub Copilot Documentation",
            url="https://docs.github.com/copilot",
            snippet="GitHub Copilot documentation and feature guides.",
        ),
        SearchResult(
            title="opencode GitHub Repository",
            url="https://github.com/sst/opencode",
            snippet="Open source agentic coding tool repository.",
        ),
    ]


def web_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    results = mock_web_search(query)
    return pre_fetch_results(results, subtask_id, limit=3)
