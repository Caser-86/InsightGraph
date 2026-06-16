import sys
from types import ModuleType

from insight_graph.state import Evidence
from insight_graph.tools.pre_fetch import pre_fetch_results
from insight_graph.tools.search_providers import (
    MockSearchProvider,
    SearchResult,
    parse_search_limit,
    search_with_providers,
)


def mock_web_search(query: str) -> list[SearchResult]:
    return MockSearchProvider().search(query, limit=3)


def web_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    limit = parse_search_limit()
    results = search_with_providers(query, limit)
    return pre_fetch_results(results, subtask_id, limit=limit, query=query)


class _CallableWebSearchModule(ModuleType):
    def __call__(self, query: str, subtask_id: str = "collect") -> list[Evidence]:
        return web_search(query, subtask_id)


sys.modules[__name__].__class__ = _CallableWebSearchModule
