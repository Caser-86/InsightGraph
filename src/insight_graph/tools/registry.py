from collections.abc import Callable

from insight_graph.state import Evidence
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.github_search import github_search
from insight_graph.tools.mock_search import mock_search
from insight_graph.tools.news_search import news_search
from insight_graph.tools.web_search import web_search

ToolFn = Callable[[str, str], list[Evidence]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {
            "fetch_url": fetch_url,
            "github_search": github_search,
            "mock_search": mock_search,
            "news_search": news_search,
            "web_search": web_search,
        }

    def run(self, name: str, query: str, subtask_id: str) -> list[Evidence]:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name](query, subtask_id)
