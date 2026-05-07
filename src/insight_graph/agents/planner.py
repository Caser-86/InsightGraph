import os
import re
from urllib.parse import urlparse

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

SOURCE_HINTS: dict[str, str] = {
    'official_site': 'official site pricing enterprise security latest 2024 2025 2026',
    'docs': 'documentation api guide latest release changelog 2024 2025 2026',
    'github': 'github repository releases tags roadmap 2024 2025 2026',
    'news': 'news launch announcement recent years 2024 2025 2026',
    'blog': 'blog analysis recent update 2024 2025 2026',
    'sec': 'sec filing investor relations recent annual quarterly 2024 2025 2026',
    'unknown': '',
}


def plan_research(state: GraphState) -> GraphState:
    research_focus = _research_focus_query(state.user_request)
    state.domain_profile = detect_domain_profile(research_focus).id
    state.resolved_entities = [
        entity.to_payload() for entity in resolve_entities(research_focus)
    ]
    state.memory_context = state.memory_context or _memory_context_for_request(
        research_focus,
        state.domain_profile,
        state.resolved_entities,
    )
    state.section_research_plan = [
        section.to_payload()
        for section in build_section_research_plan(
            profile=get_domain_profile(state.domain_profile),
            resolved_entities=state.resolved_entities,
        )
    ]
    collection_tools = _collection_tool_names(state.user_request)
    state.query_strategies = _build_query_strategies(
        research_focus,
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


def _research_focus_query(user_request: str) -> str:
    topic_match = re.search(
        r"(?:主题|topic|subject)\s*[:：]\s*(?P<topic>[^\r\n。;；]+)",
        user_request,
        flags=re.IGNORECASE,
    )
    if topic_match is not None:
        topic = _clean_query_text(topic_match.group("topic"))
        if topic:
            return topic

    useful_lines = []
    for raw_line in user_request.splitlines():
        line = _clean_query_text(raw_line)
        if not line or _is_instruction_line(line):
            continue
        useful_lines.append(line)
    if useful_lines:
        return " ".join(useful_lines)
    return _clean_query_text(user_request) or user_request.strip()


def _clean_query_text(value: str) -> str:
    return " ".join(value.strip().strip("。.;；:：").split())


def _is_instruction_line(line: str) -> bool:
    lowered = line.lower()
    if re.match(r"^\d+[.)、:：]\s*", line):
        return True
    if re.match(r"^[-*•]\s+", line):
        return True
    instruction_markers = (
        "要求",
        "重点分析",
        "输出 markdown",
        "输出markdown",
        "生成一份",
        "文章包含",
        "关键判断",
        "不要空泛",
        "先搜索",
        "output markdown",
        "write in markdown",
        "requirements",
    )
    return any(marker in lowered for marker in instruction_markers)


def _memory_context_for_request(
    user_request: str,
    domain_profile: str,
    resolved_entities: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not _is_truthy_env("INSIGHT_GRAPH_USE_MEMORY_CONTEXT"):
        return []
    store = get_research_memory_store()
    config = memory_embedding_config()
    metadata_filter = {
        **embedding_metadata_filter(config),
        "domain_profile": domain_profile,
        "support_status": ["supported", "fresh_evidence"],
        "expired": False,
    }
    entity_ids = _memory_entity_ids(resolved_entities)
    if entity_ids:
        metadata_filter["entity_id"] = entity_ids
    records = store.search(
        embed_text(user_request, config=config),
        limit=3,
        metadata_filter=metadata_filter,
    )
    return [_memory_record_payload(record) for record in records]


def _memory_entity_ids(resolved_entities: list[dict[str, object]]) -> list[str]:
    entity_ids = []
    for entity in resolved_entities:
        entity_id = entity.get("id")
        if isinstance(entity_id, str) and entity_id:
            entity_ids.append(entity_id)
    return entity_ids


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
                    "outline_questions": _section_questions(section),
                    "round": round_index,
                    "reason": "section_source_requirement",
                }
            )
    if round_index == 1 and len(entity_names) > 1:
        strategies.extend(
            _build_cross_entity_compare_strategies(
                user_request,
                section_plan,
                collection_tools,
                entity_names,
                entity_aliases,
                official_domains,
            )
        )
    if round_index == 1 and len(entity_names) == 1:
        strategies.extend(
            _build_single_entity_deep_dive_strategies(
                user_request,
                section_plan,
                collection_tools,
                entity_names,
                entity_aliases,
                official_domains,
            )
        )
    return strategies


def _build_cross_entity_compare_strategies(
    user_request: str,
    section_plan: list[dict[str, object]],
    collection_tools: list[str],
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> list[dict[str, object]]:
    strategies: list[dict[str, object]] = []
    if collection_tools == ["mock_search"]:
        return strategies
    for section in section_plan:
        section_id = str(section.get("section_id", "")).strip()
        source_types = _section_source_types(section)
        source_type = source_types[0] if source_types else "unknown"
        tool_name = _tool_for_source_type(source_type, collection_tools)
        if tool_name is None:
            continue
        strategies.append(
            {
                "strategy_id": _strategy_id(
                    2,
                    section_id,
                    source_type,
                    len(strategies) + 1,
                ),
                "section_id": section_id,
                "tool_name": tool_name,
                "query": _cross_entity_compare_query(
                    user_request,
                    section,
                    source_type,
                    entity_names,
                    entity_aliases,
                    official_domains,
                ),
                "source_type": source_type,
                "entity_names": entity_names,
                "outline_questions": _section_questions(section),
                "round": 2,
                "reason": "cross_entity_compare",
            }
        )
    return strategies


def _build_single_entity_deep_dive_strategies(
    user_request: str,
    section_plan: list[dict[str, object]],
    collection_tools: list[str],
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> list[dict[str, object]]:
    strategies: list[dict[str, object]] = []
    if collection_tools == ["mock_search"]:
        return strategies
    for section in section_plan:
        section_id = str(section.get("section_id", "")).strip()
        preferred_source = _single_entity_source_type(section)
        tool_name = _tool_for_source_type(preferred_source, collection_tools)
        if tool_name is None:
            continue
        strategies.append(
            {
                "strategy_id": _strategy_id(
                    1,
                    section_id,
                    preferred_source,
                    10_000 + len(strategies) + 1,
                ),
                "section_id": section_id,
                "tool_name": tool_name,
                "query": _single_entity_deep_dive_query(
                    user_request,
                    section,
                    preferred_source,
                    entity_names,
                    entity_aliases,
                    official_domains,
                ),
                "source_type": preferred_source,
                "entity_names": entity_names,
                "outline_questions": _section_questions(section),
                "round": 1,
                "reason": "single_entity_deep_dive",
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
        elif request_type == "missing_entity_evidence":
            source_types = _string_values(request.get("missing_source_types", []))
            for source_type in (source_types or ["official_site"]):
                tool_name = _tool_for_source_type(source_type, collection_tools)
                if tool_name is None:
                    continue
                strategies.append(
                    {
                        "strategy_id": _strategy_id(
                            round_index,
                            "missing-entity",
                            source_type,
                            len(strategies) + 1,
                        ),
                        "section_id": "missing-entity",
                        "tool_name": tool_name,
                        "query": _replan_missing_entity_query(
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
                        "reason": "missing_entity_evidence",
                    }
                )
    return strategies


def _section_source_types(section: dict[str, object]) -> list[str]:
    values = section.get("required_source_types", [])
    if not isinstance(values, list):
        return ["unknown"]
    source_types = [value for value in values if isinstance(value, str) and value]
    return source_types or ["unknown"]


def _section_questions(section: dict[str, object]) -> list[str]:
    values = section.get("questions", [])
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and value]


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
    parts = [_compact_query_seed(user_request)]
    section_id = str(section.get("section_id", "")).strip()
    title = str(section.get("title", "")).strip()
    if title:
        parts.append(_collapse_terms(title))
    elif section_id:
        parts.append(_collapse_terms(section_id.replace("-", " ")))
    source_hint = SOURCE_HINTS.get(source_type, "")
    if source_hint:
        parts.append(source_hint)
    question = _first_query_question(section)
    if question:
        parts.append(_collapse_terms(question))
    entity_hint = _entity_search_hint(entity_names, entity_aliases)
    if entity_hint:
        parts.append(entity_hint)
    domain_hint = _domain_search_hint(official_domains)
    if domain_hint:
        parts.append(domain_hint)
    return _join_query_parts(parts)


def _cross_entity_compare_query(
    user_request: str,
    section: dict[str, object],
    source_type: str,
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> str:
    parts = [_compact_query_seed(user_request)]
    parts.append("cross company comparison gap verification")
    section_id = str(section.get("section_id", "")).strip()
    title = str(section.get("title", "")).strip()
    if title:
        parts.append(_collapse_terms(title))
    elif section_id:
        parts.append(_collapse_terms(section_id.replace("-", " ")))
    source_hint = SOURCE_HINTS.get(source_type, "")
    if source_hint:
        parts.append(source_hint)
    question = _first_query_question(section)
    if question:
        parts.append(_collapse_terms(question))
    entity_hint = _entity_search_hint(entity_names, entity_aliases)
    if entity_hint:
        parts.append(entity_hint)
    domain_hint = _domain_search_hint(official_domains)
    if domain_hint:
        parts.append(domain_hint)
    return _join_query_parts(parts)


def _single_entity_deep_dive_query(
    user_request: str,
    section: dict[str, object],
    source_type: str,
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> str:
    parts = [_compact_query_seed(user_request)]
    parts.append("single company deep dive evidence details")
    section_id = str(section.get("section_id", "")).strip()
    title = str(section.get("title", "")).strip()
    if title:
        parts.append(_collapse_terms(title))
    elif section_id:
        parts.append(_collapse_terms(section_id.replace("-", " ")))
    source_hint = SOURCE_HINTS.get(source_type, "")
    if source_hint:
        parts.append(source_hint)
    parts.append("pricing roadmap integration security enterprise")
    question = _first_query_question(section)
    if question:
        parts.append(_collapse_terms(question))
    entity_hint = _entity_search_hint(entity_names, entity_aliases)
    if entity_hint:
        parts.append(entity_hint)
    domain_hint = _domain_search_hint(official_domains)
    if domain_hint:
        parts.append(domain_hint)
    return _join_query_parts(parts)


def _single_entity_source_type(section: dict[str, object]) -> str:
    source_types = _section_source_types(section)
    if "official_site" in source_types:
        return "official_site"
    if "docs" in source_types:
        return "docs"
    return source_types[0] if source_types else "unknown"


def _replan_missing_evidence_query(
    user_request: str,
    request: dict[str, object],
    source_type: str,
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> str:
    parts = [_compact_query_seed(user_request)]
    section_id = str(request.get("section_id", "")).strip()
    if section_id:
        parts.append(_collapse_terms(section_id.replace("-", " ")))
    source_hint = SOURCE_HINTS.get(source_type, "")
    if source_hint:
        parts.append(source_hint)
    parts.append("evidence gap fill")
    entity_hint = _entity_search_hint(entity_names, entity_aliases)
    if entity_hint:
        parts.append(entity_hint)
    domain_hint = _domain_search_hint(official_domains)
    if domain_hint:
        parts.append(domain_hint)
    return _join_query_parts(parts)


def _replan_unsupported_claim_query(
    user_request: str,
    request: dict[str, object],
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> str:
    parts = [_compact_query_seed(user_request)]
    claim = request.get("claim")
    if isinstance(claim, str) and claim:
        parts.append(_collapse_terms(claim))
    parts.append("evidence verification")
    entity_hint = _entity_search_hint(entity_names, entity_aliases)
    if entity_hint:
        parts.append(entity_hint)
    domain_hint = _domain_search_hint(official_domains)
    if domain_hint:
        parts.append(domain_hint)
    return _join_query_parts(parts)


def _replan_missing_entity_query(
    user_request: str,
    request: dict[str, object],
    source_type: str,
    entity_names: list[str],
    entity_aliases: list[str],
    official_domains: list[str],
) -> str:
    parts = [_compact_query_seed(user_request)]
    missing_entity = request.get("missing_entity")
    if isinstance(missing_entity, str) and missing_entity:
        parts.append(_collapse_terms(missing_entity))
    source_hint = SOURCE_HINTS.get(source_type, "")
    if source_hint:
        parts.append(source_hint)
    parts.append("product specific evidence")
    entity_hint = _entity_search_hint(entity_names, entity_aliases)
    if entity_hint:
        parts.append(entity_hint)
    preferred_domains = _string_values(request.get("preferred_domains", []))
    domain_hint = _domain_search_hint(preferred_domains or official_domains)
    if domain_hint:
        parts.append(domain_hint)
    return _join_query_parts(parts)


def _first_query_question(section: dict[str, object]) -> str:
    questions = _section_questions(section)
    if not questions:
        return ""
    return questions[0]


def _compact_query_seed(user_request: str) -> str:
    seed = _collapse_terms(user_request)
    tokens = seed.split()
    if len(tokens) <= 22:
        return seed
    return " ".join(tokens[:22])


def _entity_search_hint(entity_names: list[str], entity_aliases: list[str]) -> str:
    names = [name for name in entity_names if name][:3]
    aliases = [alias for alias in entity_aliases if alias and alias not in names][:2]
    terms = names + aliases
    return " ".join(_collapse_terms(term) for term in terms if term)


def _domain_search_hint(official_domains: list[str]) -> str:
    seen: list[str] = []
    for domain in official_domains:
        host = _normalize_domain_host(domain)
        if host and host not in seen:
            seen.append(host)
        if len(seen) >= 4:
            break
    if not seen:
        return ""
    return " ".join(f"site:{domain}" for domain in seen)


def _normalize_domain_host(value: str) -> str:
    raw = value.strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    host = parsed.netloc or parsed.path.split("/", maxsplit=1)[0]
    host = host.split("@", maxsplit=1)[-1].split(":", maxsplit=1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def _collapse_terms(value: str) -> str:
    return " ".join(re.findall(r"[A-Za-z0-9_.:/+-]+|[\u4e00-\u9fff]+", value)).strip()


def _join_query_parts(parts: list[str]) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    return " ".join(cleaned)


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



