from insight_graph.agents.relevance import (
    filter_relevant_evidence,
    is_relevance_filter_enabled,
)
from insight_graph.report_quality.evidence_scoring import score_evidence
from insight_graph.state import Evidence, GraphState, LLMCallRecord, Subtask, ToolCallRecord
from insight_graph.tools import ToolRegistry

WEB_SEARCH_TOOL = "web_search"
MOCK_SEARCH_TOOL = "mock_search"
WEB_SEARCH_EMPTY_FALLBACK_ERROR = (
    "web_search returned no evidence; falling back to mock_search"
)
WEB_SEARCH_FALLBACK_NOTE = "fallback for web_search"


def execute_subtasks(state: GraphState) -> GraphState:
    registry = ToolRegistry()
    collected: list[Evidence] = _existing_retry_evidence(state)
    records = [ToolCallRecord.model_validate(record) for record in state.tool_call_log]
    filter_enabled = is_relevance_filter_enabled()
    query = _collection_query(state)

    for subtask in state.subtasks:
        for tool_name in subtask.suggested_tools:
            kept_results, new_records = _run_tool_with_fallback(
                registry,
                tool_name,
                query,
                subtask,
                filter_enabled,
                state.llm_call_log,
            )
            collected.extend(kept_results)
            records.extend(new_records)

    deduped = _deduplicate_evidence(collected)
    ordered_evidence, evidence_scores = _order_evidence_by_score(deduped)
    state.evidence_pool = ordered_evidence
    state.global_evidence_pool = ordered_evidence
    state.tool_call_log = records
    state.evidence_scores = evidence_scores
    state.section_collection_status = _build_section_collection_status(
        state.section_research_plan,
        ordered_evidence,
    )
    return state


def _existing_retry_evidence(state: GraphState) -> list[Evidence]:
    if state.iterations <= 0 or not state.replan_requests:
        return []
    existing = state.global_evidence_pool or state.evidence_pool
    return [Evidence.model_validate(item) for item in existing]


def _collection_query(state: GraphState) -> str:
    if state.iterations <= 0 or not state.replan_requests:
        return state.user_request

    parts = [state.user_request]
    for request in state.replan_requests:
        if request.get("type") != "missing_section_evidence":
            continue
        section_id = str(request.get("section_id", "")).strip()
        missing_evidence = int(request.get("missing_evidence", 0))
        missing_source_types = _string_list(request.get("missing_source_types", []))
        if section_id:
            parts.append(f"section: {section_id}")
        if missing_source_types:
            parts.append(f"missing source types: {', '.join(missing_source_types)}")
        if missing_evidence > 0:
            parts.append(f"missing evidence: {missing_evidence}")
        break
    return " | ".join(parts)


def _string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and value]


def _build_section_collection_status(
    section_plan: list[dict[str, object]],
    evidence: list[Evidence],
) -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []
    evidence_count = len(evidence)
    for section in section_plan:
        min_evidence = int(section.get("min_evidence", 1))
        missing_evidence = max(0, min_evidence - evidence_count)
        required_source_types = _required_source_types(section)
        covered_source_types = _covered_source_types(required_source_types, evidence)
        missing_source_types = [
            source_type
            for source_type in required_source_types
            if source_type not in covered_source_types
        ]
        statuses.append(
            {
                "section_id": str(section.get("section_id", "")),
                "round": 1,
                "evidence_count": evidence_count,
                "min_evidence": min_evidence,
                "required_source_types": required_source_types,
                "covered_source_types": covered_source_types,
                "missing_source_types": missing_source_types,
                "sufficient": missing_evidence == 0 and not missing_source_types,
                "missing_evidence": missing_evidence,
            }
        )
    return statuses


def _required_source_types(section: dict[str, object]) -> list[str]:
    raw_values = section.get("required_source_types", [])
    if not isinstance(raw_values, list):
        return []
    return [value for value in raw_values if isinstance(value, str) and value]


def _covered_source_types(
    required_source_types: list[str],
    evidence: list[Evidence],
) -> list[str]:
    available_source_types = {item.source_type for item in evidence if item.verified}
    return [
        source_type
        for source_type in required_source_types
        if source_type in available_source_types
    ]


def _run_tool_with_fallback(
    registry: ToolRegistry,
    tool_name: str,
    query: str,
    subtask: Subtask,
    filter_enabled: bool,
    llm_call_log: list[LLMCallRecord],
) -> tuple[list[Evidence], list[ToolCallRecord]]:
    try:
        results = registry.run(tool_name, query, subtask.id)
    except Exception as exc:
        failed_record = ToolCallRecord(
            subtask_id=subtask.id,
            tool_name=tool_name,
            query=query,
            success=False,
            error=str(exc),
        )
        if tool_name != WEB_SEARCH_TOOL:
            return [], [failed_record]
        fallback_results, fallback_records = _run_mock_search_fallback(
            registry, query, subtask, filter_enabled, llm_call_log
        )
        return fallback_results, [failed_record, *fallback_records]

    if tool_name == WEB_SEARCH_TOOL and not results:
        failed_record = ToolCallRecord(
            subtask_id=subtask.id,
            tool_name=tool_name,
            query=query,
            success=False,
            error=WEB_SEARCH_EMPTY_FALLBACK_ERROR,
        )
        fallback_results, fallback_records = _run_mock_search_fallback(
            registry, query, subtask, filter_enabled, llm_call_log
        )
        return fallback_results, [failed_record, *fallback_records]

    kept_results, filtered_count = _process_tool_results(
        query, subtask, results, filter_enabled, llm_call_log
    )
    return kept_results, [
        ToolCallRecord(
            subtask_id=subtask.id,
            tool_name=tool_name,
            query=query,
            evidence_count=len(results),
            filtered_count=filtered_count,
        )
    ]


def _process_tool_results(
    query: str,
    subtask: Subtask,
    results: list[Evidence],
    filter_enabled: bool,
    llm_call_log: list[LLMCallRecord],
) -> tuple[list[Evidence], int]:
    deduped_results = _deduplicate_evidence(results)
    if not filter_enabled:
        return deduped_results, 0
    return filter_relevant_evidence(
        query,
        subtask,
        deduped_results,
        llm_call_log=llm_call_log,
    )


def _run_mock_search_fallback(
    registry: ToolRegistry,
    query: str,
    subtask: Subtask,
    filter_enabled: bool,
    llm_call_log: list[LLMCallRecord],
) -> tuple[list[Evidence], list[ToolCallRecord]]:
    try:
        results = registry.run(MOCK_SEARCH_TOOL, query, subtask.id)
    except Exception as exc:
        return [], [
            ToolCallRecord(
                subtask_id=subtask.id,
                tool_name=MOCK_SEARCH_TOOL,
                query=query,
                success=False,
                error=f"fallback for web_search failed: {exc}",
            )
        ]

    kept_results, filtered_count = _process_tool_results(
        query, subtask, results, filter_enabled, llm_call_log
    )
    return kept_results, [
        ToolCallRecord(
            subtask_id=subtask.id,
            tool_name=MOCK_SEARCH_TOOL,
            query=query,
            evidence_count=len(results),
            filtered_count=filtered_count,
            error=WEB_SEARCH_FALLBACK_NOTE,
        )
    ]


def _deduplicate_evidence(evidence: list[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str]] = set()
    deduped: list[Evidence] = []
    for item in evidence:
        key = (item.id, item.source_url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _order_evidence_by_score(
    evidence: list[Evidence],
) -> tuple[list[Evidence], list[dict[str, object]]]:
    scored = [(score_evidence(item), index, item) for index, item in enumerate(evidence)]
    scored.sort(key=lambda item: (-int(item[0]["overall_score"]), item[1]))
    return [item for _, _, item in scored], [score for score, _, _ in scored]
