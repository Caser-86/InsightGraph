import os

from insight_graph.memory.embeddings import embed_text, memory_embedding_config
from insight_graph.memory.store import ResearchMemoryRecord, get_research_memory_store
from insight_graph.report_quality.domain_profiles import detect_domain_profile, get_domain_profile
from insight_graph.report_quality.entity_resolver import resolve_entities
from insight_graph.report_quality.research_plan import build_section_research_plan
from insight_graph.state import GraphState, Subtask
from insight_graph.tools.sec_filings import has_sec_filing_target


def plan_research(state: GraphState) -> GraphState:
    state.memory_context = state.memory_context or _memory_context_for_request(state.user_request)
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
            description=_collection_description(state),
            subtask_type="research",
            dependencies=["scope"],
            suggested_tools=_collection_tool_names(state.user_request),
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


def _memory_context_for_request(user_request: str) -> list[dict[str, object]]:
    if not _is_truthy_env("INSIGHT_GRAPH_USE_MEMORY_CONTEXT"):
        return []
    store = get_research_memory_store()
    records = store.search(
        embed_text(user_request, config=memory_embedding_config()),
        limit=3,
    )
    return [_memory_record_payload(record) for record in records]


def _memory_record_payload(record: ResearchMemoryRecord) -> dict[str, object]:
    return {
        "memory_id": record.memory_id,
        "text": record.text,
        "metadata": dict(record.metadata),
    }


def _collection_description(state: GraphState) -> str:
    parts = ["Collect evidence about product positioning, features, pricing, and sources"]
    if state.memory_context:
        count = len(state.memory_context)
        suffix = "item" if count == 1 else "items"
        parts.append(f"Use {count} retrieved memory context {suffix} to guide collection")
    if state.tried_strategies:
        parts.append(f"Avoid tried strategies: {', '.join(state.tried_strategies)}")
    return ". ".join(parts)


def _collection_tool_names(user_request: str) -> list[str]:
    if _is_truthy_env("INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION"):
        tools = []
        if _is_truthy_env("INSIGHT_GRAPH_USE_WEB_SEARCH"):
            tools.append("web_search")
        if _is_truthy_env("INSIGHT_GRAPH_USE_GITHUB_SEARCH"):
            tools.append("github_search")
        if _is_truthy_env("INSIGHT_GRAPH_USE_NEWS_SEARCH"):
            tools.append("news_search")
        if _is_truthy_env("INSIGHT_GRAPH_USE_SEC_FILINGS") and has_sec_filing_target(
            user_request
        ):
            tools.append("sec_filings")
        if _is_truthy_env("INSIGHT_GRAPH_USE_SEC_FINANCIALS") and has_sec_filing_target(
            user_request
        ):
            tools.append("sec_financials")
        if tools:
            return tools

    return [_collection_tool_name(user_request)]


def _collection_tool_name(user_request: str) -> str:
    if _is_truthy_env("INSIGHT_GRAPH_USE_WEB_SEARCH"):
        return "web_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_GITHUB_SEARCH"):
        return "github_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_NEWS_SEARCH"):
        return "news_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_SEC_FILINGS") and has_sec_filing_target(
        user_request
    ):
        return "sec_filings"
    if _is_truthy_env("INSIGHT_GRAPH_USE_SEC_FINANCIALS") and has_sec_filing_target(
        user_request
    ):
        return "sec_financials"
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
