from importlib import import_module

from insight_graph.tools.document_reader import document_reader
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.file_tools import list_directory, read_file, write_file
from insight_graph.tools.github_search import github_search
from insight_graph.tools.news_search import news_search
from insight_graph.tools.registry import ToolRegistry
from insight_graph.tools.web_search import SearchResult

web_search = import_module("insight_graph.tools.web_search")

__all__ = [
    "SearchResult",
    "ToolRegistry",
    "document_reader",
    "fetch_url",
    "github_search",
    "list_directory",
    "news_search",
    "read_file",
    "web_search",
    "write_file",
]
