import sys
from types import ModuleType

from insight_graph.state import Evidence
from insight_graph.tools.pre_fetch import pre_fetch_results
from insight_graph.tools.search_providers import (
    MockSearchProvider,
    SearchResult,
    get_search_provider,
    parse_search_limit,
)


def mock_web_search(query: str) -> list[SearchResult]:
    return MockSearchProvider().search(query, limit=3)


def web_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    limit = parse_search_limit()
    results = get_search_provider().search(query, limit)
    return pre_fetch_results(results, subtask_id, limit=limit)


class _CallableWebSearchModule(ModuleType):
    def __call__(self, query: str, subtask_id: str = "collect") -> list[Evidence]:
        return web_search(query, subtask_id)


sys.modules[__name__].__class__ = _CallableWebSearchModule
