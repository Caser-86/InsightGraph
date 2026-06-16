from collections.abc import Callable

from insight_graph.state import Evidence
from insight_graph.tools.document_reader import document_reader
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.file_tools import list_directory, read_file, write_file
from insight_graph.tools.github_search import github_search
from insight_graph.tools.mock_search import mock_search
from insight_graph.tools.news_search import news_search
from insight_graph.tools.search_document import search_document
from insight_graph.tools.sec_filings import sec_filings, sec_financials
from insight_graph.tools.web_search import web_search

ToolFn = Callable[[str, str], list[Evidence]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {
            "document_reader": document_reader,
            "fetch_url": fetch_url,
            "github_search": github_search,
            "list_directory": list_directory,
            "mock_search": mock_search,
            "news_search": news_search,
            "read_file": read_file,
            "search_document": search_document,
            "sec_filings": sec_filings,
            "sec_financials": sec_financials,
            "web_search": web_search,
            "write_file": write_file,
        }

    def run(self, name: str, query: str, subtask_id: str) -> list[Evidence]:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name](query, subtask_id)
