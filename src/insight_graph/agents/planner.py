import os

from insight_graph.memory.embeddings import (
    embed_text,
    embedding_metadata_filter,
    memory_embedding_config,
)
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
    collection_tools = _collection_tool_names(state.user_request)
    state.query_strategies = _build_query_strategies(
        state.user_request,
        state.section_research_plan,
        state.resolved_entities,
        collection_tools,
        state.iterations + 1,
        state.replan_requests,
    )
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
            suggested_tools=collection_tools,
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
    config = memory_embedding_config()
    records = store.search(
        embed_text(user_request, config=config),
        limit=3,
        metadata_filter=embedding_metadata_filter(config),
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
    if _is_truthy_env("INSIGHT_GRAPH_USE_SEARCH_DOCUMENT"):
        return "search_document"
    if _is_truthy_env("INSIGHT_GRAPH_USE_DOCUMENT_READER"):
        return "document_reader"
    if _is_truthy_env("INSIGHT_GRAPH_USE_READ_FILE"):
        return "read_file"
    if _is_truthy_env("INSIGHT_GRAPH_USE_LIST_DIRECTORY"):
        return "list_directory"
    if _is_truthy_env("INSIGHT_GRAPH_USE_WRITE_FILE"):
        return "write_file"
    return "mock_search"


def _build_query_strategies(
    user_request: str,
    section_plan: list[dict[str, object]],
    resolved_entities: list[dict[str, object]],
    collection_tools: list[str],
    round_index: int,
    replan_requests: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    strategies: list[dict[str, object]] = []
    entity_names = _entity_names(resolved_entities)
    entity_aliases = _entity_aliases(resolved_entities)
    official_domains = _official_domains(resolved_entities)
    if round_index > 1 and replan_requests:
        return _build_replan_query_strategies(
            user_request,
            replan_requests,
            collection_tools,
            round_index,
            entity_names,
            entity_aliases,
            official_domains,
        )
    if collection_tools == ["mock_search"]:
        return []
    for section in section_plan:
        section_id = str(section.get("section_id", "")).strip()
        source_types = _section_source_types(section)
        for source_type in source_types:
            tool_name = _tool_for_source_type(source_type, collection_tools)
            if tool_name is None:
                continue
            strategies.append(
                {
                    "strategy_id": _strategy_id(
                        round_index,
                        section_id,
                        source_type,
                        len(strategies) + 1,
                    ),
                    "section_id": section_id,
                    "tool_name": tool_name,
                    "query": _strategy_query(
                        user_request,
                        section,
                        source_type,
                        entity_names,
                        entity_aliases,
                        official_domains,
                    ),
                    "source_type": source_type,
                    "entity_names": entity_names,
                    "round": round_index,
                    "reason": "section_source_requirement",
                }
            )
    return strategies


def _build_replan_query_strategies(
    user_request: str,
    replan_requests: list[dict[str, object]],
    collection_tools: list[str],
    round_index: int,
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> list[dict[str, object]]:
    strategies: list[dict[str, object]] = []
    for request in replan_requests:
        request_type = request.get("type")
        if request_type == "missing_section_evidence":
            missing_source_types = _string_values(request.get("missing_source_types", []))
            source_types = missing_source_types or ["unknown"]
            section_id = str(request.get("section_id", "")).strip()
            for source_type in source_types:
                tool_name = _tool_for_source_type(source_type, collection_tools)
                if tool_name is None:
                    continue
                strategies.append(
                    {
                        "strategy_id": _strategy_id(
                            round_index,
                            section_id,
                            source_type,
                            len(strategies) + 1,
                        ),
                        "section_id": section_id,
                        "tool_name": tool_name,
                        "query": _replan_missing_evidence_query(
                            user_request,
                            request,
                            source_type,
                            entity_names,
                            entity_aliases,
                            official_domains,
                        ),
                        "source_type": source_type,
                        "entity_names": entity_names,
                        "round": round_index,
                        "reason": "missing_section_evidence",
                    }
                )
        elif request_type == "unsupported_claim":
            tool_name = _tool_for_source_type("official_site", collection_tools)
            if tool_name is None:
                continue
            strategies.append(
                {
                    "strategy_id": _strategy_id(
                        round_index,
                        "unsupported-claim",
                        "official_site",
                        len(strategies) + 1,
                    ),
                    "section_id": "unsupported-claim",
                    "tool_name": tool_name,
                    "query": _replan_unsupported_claim_query(
                        user_request,
                        request,
                        entity_names,
                        entity_aliases,
                        official_domains,
                    ),
                    "source_type": "official_site",
                    "entity_names": entity_names,
                    "round": round_index,
                    "reason": "unsupported_claim",
                }
            )
    return strategies


def _section_source_types(section: dict[str, object]) -> list[str]:
    values = section.get("required_source_types", [])
    if not isinstance(values, list):
        return ["unknown"]
    source_types = [value for value in values if isinstance(value, str) and value]
    return source_types or ["unknown"]


def _tool_for_source_type(source_type: str, collection_tools: list[str]) -> str | None:
    preferred_tools = {
        "github": "github_search",
        "news": "news_search",
        "sec": "sec_filings",
        "docs": "document_reader",
    }
    preferred_tool = preferred_tools.get(source_type)
    if preferred_tool in collection_tools:
        return preferred_tool
    if "web_search" in collection_tools:
        return "web_search"
    return collection_tools[0] if collection_tools else None


def _strategy_query(
    user_request: str,
    section: dict[str, object],
    source_type: str,
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> str:
    parts = [user_request]
    section_id = str(section.get("section_id", "")).strip()
    title = str(section.get("title", "")).strip()
    if section_id:
        parts.append(f"section: {section_id}")
    if title:
        parts.append(f"title: {title}")
    if source_type:
        parts.append(f"source type: {source_type}")
    if entity_names:
        parts.append(f"entities: {', '.join(entity_names)}")
    if entity_aliases:
        parts.append(f"aliases: {', '.join(entity_aliases)}")
    if official_domains:
        parts.append(f"official domains: {', '.join(official_domains)}")
    return " | ".join(parts)


def _replan_missing_evidence_query(
    user_request: str,
    request: dict[str, object],
    source_type: str,
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> str:
    parts = [user_request]
    section_id = str(request.get("section_id", "")).strip()
    if section_id:
        parts.append(f"section: {section_id}")
    parts.append(f"source type: {source_type}")
    missing_source_types = _string_values(request.get("missing_source_types", []))
    if missing_source_types:
        parts.append(f"missing source types: {', '.join(missing_source_types)}")
    missing_evidence = request.get("missing_evidence")
    if isinstance(missing_evidence, int):
        parts.append(f"missing evidence: {missing_evidence}")
    parts.extend(_entity_query_parts(entity_names, entity_aliases, official_domains))
    return " | ".join(parts)


def _replan_unsupported_claim_query(
    user_request: str,
    request: dict[str, object],
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> str:
    parts = [user_request]
    claim = request.get("claim")
    if isinstance(claim, str) and claim:
        parts.append(f"unsupported claim: {claim}")
    reason = request.get("reason")
    if isinstance(reason, str) and reason:
        parts.append(f"reason: {reason}")
    parts.extend(_entity_query_parts(entity_names, entity_aliases, official_domains))
    return " | ".join(parts)


def _entity_query_parts(
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> list[str]:
    parts = []
    if entity_names:
        parts.append(f"entities: {', '.join(entity_names)}")
    if entity_aliases:
        parts.append(f"aliases: {', '.join(entity_aliases)}")
    if official_domains:
        parts.append(f"official domains: {', '.join(official_domains)}")
    return parts


def _entity_names(resolved_entities: list[dict[str, object]]) -> list[str]:
    names = []
    for entity in resolved_entities:
        name = entity.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _entity_aliases(resolved_entities: list[dict[str, object]]) -> list[str]:
    aliases: list[str] = []
    for entity in resolved_entities:
        for alias in _string_values(entity.get("aliases", [])):
            if alias not in aliases:
                aliases.append(alias)
    return aliases


def _official_domains(resolved_entities: list[dict[str, object]]) -> list[str]:
    domains: list[str] = []
    for entity in resolved_entities:
        for domain in _string_values(entity.get("official_domains", [])):
            if domain not in domains:
                domains.append(domain)
    return domains


def _string_values(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and value]


def _strategy_id(
    round_index: int,
    section_id: str,
    source_type: str,
    sequence: int,
) -> str:
    return f"r{round_index}-{section_id or 'section'}-{source_type}-{sequence}"


def _is_truthy_env(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes"}
