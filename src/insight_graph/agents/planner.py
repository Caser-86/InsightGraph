import os

from insight_graph.report_quality.domain_profiles import detect_domain_profile, get_domain_profile
from insight_graph.report_quality.entity_resolver import resolve_entities
from insight_graph.report_quality.research_plan import build_section_research_plan
from insight_graph.state import GraphState, Subtask


def plan_research(state: GraphState) -> GraphState:
    state.domain_profile = detect_domain_profile(state.user_request).id
    state.resolved_entities = [
        entity.to_payload() for entity in resolve_entities(state.user_request)
    ]
    state.section_research_plan = [
        section.to_payload()
        for section in build_section_research_plan(
            profile=get_domain_profile(state.domain_profile),
            resolved_entities=state.resolved_entities,
        )
    ]
    state.subtasks = [
        Subtask(
            id="scope",
            description="Identify key products, companies, and scope from the user request",
            subtask_type="research",
        ),
        Subtask(
            id="collect",
            description=(
                "Collect evidence about product positioning, features, pricing, and sources"
            ),
            subtask_type="research",
            dependencies=["scope"],
            suggested_tools=_collection_tool_names(),
        ),
        Subtask(
            id="analyze",
            description="Analyze competitive patterns, differentiators, risks, and trends",
            subtask_type="synthesis",
            dependencies=["collect"],
        ),
        Subtask(
            id="report",
            description="Synthesize findings into a cited research report",
            subtask_type="synthesis",
            dependencies=["analyze"],
        ),
    ]
    return state


def _collection_tool_names() -> list[str]:
    if _is_truthy_env("INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION"):
        tools = []
        if _is_truthy_env("INSIGHT_GRAPH_USE_WEB_SEARCH"):
            tools.append("web_search")
        if _is_truthy_env("INSIGHT_GRAPH_USE_GITHUB_SEARCH"):
            tools.append("github_search")
        if _is_truthy_env("INSIGHT_GRAPH_USE_NEWS_SEARCH"):
            tools.append("news_search")
        if _is_truthy_env("INSIGHT_GRAPH_USE_SEC_FILINGS"):
            tools.append("sec_filings")
        if tools:
            return tools

    return [_collection_tool_name()]


def _collection_tool_name() -> str:
    if _is_truthy_env("INSIGHT_GRAPH_USE_WEB_SEARCH"):
        return "web_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_GITHUB_SEARCH"):
        return "github_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_NEWS_SEARCH"):
        return "news_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_SEC_FILINGS"):
        return "sec_filings"
    if _is_truthy_env("INSIGHT_GRAPH_USE_DOCUMENT_READER"):
        return "document_reader"
    if _is_truthy_env("INSIGHT_GRAPH_USE_READ_FILE"):
        return "read_file"
    if _is_truthy_env("INSIGHT_GRAPH_USE_LIST_DIRECTORY"):
        return "list_directory"
    if _is_truthy_env("INSIGHT_GRAPH_USE_WRITE_FILE"):
        return "write_file"
    return "mock_search"


def _is_truthy_env(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes"}
