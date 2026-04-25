from insight_graph.agents.relevance import (
    filter_relevant_evidence,
    is_relevance_filter_enabled,
)
from insight_graph.state import Evidence, GraphState, ToolCallRecord
from insight_graph.tools import ToolRegistry


def execute_subtasks(state: GraphState) -> GraphState:
    registry = ToolRegistry()
    collected: list[Evidence] = []
    records = [ToolCallRecord.model_validate(record) for record in state.tool_call_log]
    filter_enabled = is_relevance_filter_enabled()

    for subtask in state.subtasks:
        for tool_name in subtask.suggested_tools:
            try:
                results = registry.run(tool_name, state.user_request, subtask.id)
            except Exception as exc:
                records.append(
                    ToolCallRecord(
                        subtask_id=subtask.id,
                        tool_name=tool_name,
                        query=state.user_request,
                        success=False,
                        error=str(exc),
                    )
                )
                continue

            deduped_results = _deduplicate_evidence(results)
            filtered_count = 0
            if filter_enabled:
                kept_results, filtered_count = filter_relevant_evidence(
                    state.user_request,
                    subtask,
                    deduped_results,
                    llm_call_log=state.llm_call_log,
                )
            else:
                kept_results = deduped_results

            collected.extend(kept_results)
            records.append(
                ToolCallRecord(
                    subtask_id=subtask.id,
                    tool_name=tool_name,
                    query=state.user_request,
                    evidence_count=len(results),
                    filtered_count=filtered_count,
                )
            )

    deduped = _deduplicate_evidence(collected)
    state.evidence_pool = deduped
    state.global_evidence_pool = deduped
    state.tool_call_log = records
    return state


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
