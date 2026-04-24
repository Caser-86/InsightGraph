from insight_graph.tools import web_search as _web_search_module
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.registry import ToolRegistry
from insight_graph.tools.web_search import SearchResult


def web_search(query: str, subtask_id: str = "collect"):
    results = web_search.mock_web_search(query)
    return web_search.pre_fetch_results(results, subtask_id, limit=3)


web_search.mock_web_search = _web_search_module.mock_web_search
web_search.pre_fetch_results = _web_search_module.pre_fetch_results
web_search.web_search = web_search

__all__ = ["SearchResult", "ToolRegistry", "fetch_url", "web_search"]
