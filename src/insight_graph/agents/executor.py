from insight_graph.agents.relevance import (
    filter_relevant_evidence,
    is_relevance_filter_enabled,
)
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
    collected: list[Evidence] = []
    records = [ToolCallRecord.model_validate(record) for record in state.tool_call_log]
    filter_enabled = is_relevance_filter_enabled()

    for subtask in state.subtasks:
        for tool_name in subtask.suggested_tools:
            kept_results, new_records = _run_tool_with_fallback(
                registry,
                tool_name,
                state.user_request,
                subtask,
                filter_enabled,
                state.llm_call_log,
            )
            collected.extend(kept_results)
            records.extend(new_records)

    deduped = _deduplicate_evidence(collected)
    state.evidence_pool = deduped
    state.global_evidence_pool = deduped
    state.tool_call_log = records
    state.section_collection_status = _build_section_collection_status(
        state.section_research_plan,
        deduped,
    )
    return state


def _build_section_collection_status(
    section_plan: list[dict[str, object]],
    evidence: list[Evidence],
) -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []
    evidence_count = len(evidence)
    for section in section_plan:
        min_evidence = int(section.get("min_evidence", 1))
        missing_evidence = max(0, min_evidence - evidence_count)
        statuses.append(
            {
                "section_id": str(section.get("section_id", "")),
                "round": 1,
                "evidence_count": evidence_count,
                "min_evidence": min_evidence,
                "sufficient": missing_evidence == 0,
                "missing_evidence": missing_evidence,
            }
        )
    return statuses


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
