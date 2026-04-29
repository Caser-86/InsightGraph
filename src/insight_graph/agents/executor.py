import os
import re

from insight_graph.agents.relevance import (
    filter_relevant_evidence,
    is_relevance_filter_enabled,
)
from insight_graph.report_quality.budgeting import get_research_budgets
from insight_graph.report_quality.evidence_scoring import score_evidence
from insight_graph.state import Evidence, GraphState, LLMCallRecord, Subtask, ToolCallRecord
from insight_graph.tools import ToolRegistry

WEB_SEARCH_TOOL = "web_search"
MOCK_SEARCH_TOOL = "mock_search"
WEB_SEARCH_EMPTY_FALLBACK_ERROR = (
    "web_search returned no evidence; falling back to mock_search"
)
WEB_SEARCH_FALLBACK_NOTE = "fallback for web_search"
MAX_EVIDENCE_PER_TOOL = 5
MAX_COLLECTION_ROUNDS_ENV = "INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS"
MAX_TOOL_ROUNDS_ENV = "INSIGHT_GRAPH_MAX_TOOL_ROUNDS"
TOOL_SOURCE_TYPES = {
    "github_search": {"github"},
    "news_search": {"news"},
    "sec_filings": {"official_site"},
    "document_reader": {"docs"},
    "web_search": {"official_site", "docs", "news", "blog", "unknown"},
}


def _max_collection_rounds() -> int:
    raw_value = os.environ.get(MAX_COLLECTION_ROUNDS_ENV, "1")
    try:
        value = int(raw_value)
    except ValueError:
        return 1
    return value if value > 0 else 1


def _max_tool_rounds() -> int:
    raw_value = os.environ.get(MAX_TOOL_ROUNDS_ENV)
    if raw_value is None:
        return _max_collection_rounds()
    try:
        value = int(raw_value)
    except ValueError:
        return _max_collection_rounds()
    return value if value > 0 else _max_collection_rounds()


def execute_subtasks(state: GraphState) -> GraphState:
    registry = ToolRegistry()
    collected: list[Evidence] = _existing_retry_evidence(state)
    records = [ToolCallRecord.model_validate(record) for record in state.tool_call_log]
    filter_enabled = is_relevance_filter_enabled()
    budgets = get_research_budgets()
    max_rounds = _max_tool_rounds()
    previous_evidence_keys: set[tuple[str, str]] = set()
    round_summaries: list[dict[str, object]] = []
    stop_reason = "max_rounds"

    for round_index in range(1, max_rounds + 1):
        section_focus = _section_focus_for_round(state, round_index)
        for subtask in state.subtasks:
            for tool_name in subtask.suggested_tools:
                if len(records) >= budgets.max_tool_calls:
                    stop_reason = "tool_budget_exhausted"
                    break
                query = _collection_query(state, tool_name, section_focus)
                section_id = _focused_section_id(section_focus)
                kept_results, new_records = _run_tool_with_fallback(
                    registry,
                    tool_name,
                    query,
                    subtask,
                    filter_enabled,
                    state.llm_call_log,
                    round_index=round_index,
                    section_id=section_id,
                )
                collected.extend(kept_results)
                records.extend(new_records)
            if stop_reason == "tool_budget_exhausted":
                break
        if stop_reason == "tool_budget_exhausted":
            state = _finalize_collected_evidence(state, collected, records)
            round_summaries.append(
                {
                    "round": round_index,
                    "new_evidence_count": 0,
                    "total_evidence_count": len(state.evidence_pool),
                    "sufficient": _all_sections_sufficient(state.section_collection_status),
                }
            )
            break

        state = _finalize_collected_evidence(state, collected, records)
        current_evidence_keys = {(item.id, item.source_url) for item in state.evidence_pool}
        new_evidence_count = len(current_evidence_keys - previous_evidence_keys)
        previous_evidence_keys = current_evidence_keys
        sufficient = _all_sections_sufficient(state.section_collection_status)
        round_summaries.append(
            {
                "round": round_index,
                "new_evidence_count": new_evidence_count,
                "total_evidence_count": len(state.evidence_pool),
                "sufficient": sufficient,
            }
        )
        if sufficient:
            stop_reason = "sufficient"
            break
        if not state.section_research_plan and max_rounds == 1:
            stop_reason = "no_section_plan"
            break
        if round_index > 1 and new_evidence_count == 0:
            stop_reason = "no_new_evidence"
            break

    state.collection_rounds = round_summaries
    state.collection_stop_reason = stop_reason
    return state


def _finalize_collected_evidence(
    state: GraphState,
    collected: list[Evidence],
    records: list[ToolCallRecord],
) -> GraphState:
    deduped = _assign_section_ids(
        _deduplicate_evidence(collected),
        state.section_research_plan,
    )
    ordered_evidence, evidence_scores = _order_evidence_by_score(deduped)
    capped_evidence = _cap_evidence_pool(ordered_evidence, state.section_research_plan)
    evidence_scores = [score_evidence(item) for item in capped_evidence]
    state.evidence_pool = capped_evidence
    state.global_evidence_pool = capped_evidence
    state.tool_call_log = records
    state.evidence_scores = evidence_scores
    state.section_collection_status = _build_section_collection_status(
        state.section_research_plan,
        capped_evidence,
    )
    return state


def _section_focus_for_round(
    state: GraphState,
    round_index: int,
) -> dict[str, object] | None:
    if round_index <= 1:
        return None
    for status in state.section_collection_status:
        if not bool(status.get("sufficient", False)):
            return status
    return None


def _focused_section_id(section_focus: dict[str, object] | None) -> str | None:
    if section_focus is None:
        return None
    section_id = section_focus.get("section_id")
    return section_id if isinstance(section_id, str) and section_id else None


def _all_sections_sufficient(statuses: list[dict[str, object]]) -> bool:
    return bool(statuses) and all(bool(status.get("sufficient", False)) for status in statuses)


def _existing_retry_evidence(state: GraphState) -> list[Evidence]:
    if state.iterations <= 0 or not state.replan_requests:
        return []
    existing = state.global_evidence_pool or state.evidence_pool
    return [Evidence.model_validate(item) for item in existing]


def _collection_query(
    state: GraphState,
    tool_name: str,
    section_focus: dict[str, object] | None = None,
) -> str:
    base_query = _section_aware_query(state, tool_name)
    parts = [base_query]
    if section_focus is not None:
        focused_section_id = _focused_section_id(section_focus)
        missing_evidence = int(section_focus.get("missing_evidence", 0))
        missing_source_types = _string_list(section_focus.get("missing_source_types", []))
        if focused_section_id:
            parts.append(f"section: {focused_section_id}")
        if missing_source_types:
            parts.append(f"missing source types: {', '.join(missing_source_types)}")
        if missing_evidence > 0:
            parts.append(f"missing evidence: {missing_evidence}")
    if state.iterations <= 0 or not state.replan_requests:
        return " | ".join(parts)

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


def _section_aware_query(state: GraphState, tool_name: str) -> str:
    parts = [state.user_request]
    entity_names = _resolved_entity_names(state.resolved_entities)
    if entity_names:
        parts.append(f"entities: {', '.join(entity_names)}")
    matching_sections = _matching_sections_for_tool(state.section_research_plan, tool_name)
    for section in matching_sections[:2]:
        section_id = str(section.get("section_id", "")).strip()
        title = str(section.get("title", "")).strip()
        question = _first_question(section)
        section_parts = []
        if section_id:
            section_parts.append(section_id)
        if title:
            section_parts.append(title)
        if question:
            section_parts.append(question)
        if section_parts:
            parts.append("section: " + " | ".join(section_parts))
    return " | ".join(parts)


def _resolved_entity_names(entities: list[dict[str, object]]) -> list[str]:
    names = []
    for entity in entities:
        name = entity.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _matching_sections_for_tool(
    section_plan: list[dict[str, object]],
    tool_name: str,
) -> list[dict[str, object]]:
    source_types = TOOL_SOURCE_TYPES.get(tool_name)
    if not source_types:
        return section_plan
    matching = [
        section
        for section in section_plan
        if source_types.intersection(_required_source_types(section))
    ]
    return matching or section_plan


def _first_question(section: dict[str, object]) -> str:
    questions = section.get("questions", [])
    if isinstance(questions, list):
        for question in questions:
            if isinstance(question, str) and question:
                return question
    return ""


def _string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and value]


def _build_section_collection_status(
    section_plan: list[dict[str, object]],
    evidence: list[Evidence],
) -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []
    for section in section_plan:
        section_id = str(section.get("section_id", ""))
        section_evidence = [item for item in evidence if item.section_id == section_id]
        evidence_count = len(section_evidence)
        min_evidence = int(section.get("min_evidence", 1))
        missing_evidence = max(0, min_evidence - evidence_count)
        required_source_types = _required_source_types(section)
        covered_source_types = _covered_source_types(required_source_types, section_evidence)
        missing_source_types = [
            source_type
            for source_type in required_source_types
            if source_type not in covered_source_types
        ]
        statuses.append(
            {
                "section_id": section_id,
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


def _assign_section_ids(
    evidence: list[Evidence],
    section_plan: list[dict[str, object]],
) -> list[Evidence]:
    if not section_plan:
        return evidence
    return [
        item.model_copy(update={"section_id": _section_id_for_evidence(item, section_plan)})
        for item in evidence
    ]


def _section_id_for_evidence(
    evidence: Evidence,
    section_plan: list[dict[str, object]],
) -> str | None:
    scored_sections = [
        (_section_match_score(evidence, section), index, section)
        for index, section in enumerate(section_plan)
    ]
    scored_sections.sort(key=lambda item: (-item[0], item[1]))
    best = scored_sections[0][2]
    section_id = best.get("section_id")
    return section_id if isinstance(section_id, str) and section_id else None


def _section_match_score(evidence: Evidence, section: dict[str, object]) -> int:
    score = 0
    if evidence.source_type in _required_source_types(section):
        score += 10
    haystack = " ".join([evidence.title, evidence.source_url, evidence.snippet]).lower()
    section_terms = _section_terms(section)
    score += sum(1 for term in section_terms if term in haystack)
    return score


def _section_terms(section: dict[str, object]) -> list[str]:
    raw_values: list[object] = [
        section.get("section_id", ""),
        section.get("title", ""),
        *_object_list(section.get("questions", [])),
    ]
    terms: list[str] = []
    for value in raw_values:
        if not isinstance(value, str):
            continue
        terms.extend(token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) >= 4)
    return list(dict.fromkeys(terms))


def _object_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


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
    *,
    round_index: int = 1,
    section_id: str | None = None,
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
            round_index=round_index,
            section_id=section_id,
        )
        if tool_name != WEB_SEARCH_TOOL:
            return [], [failed_record]
        fallback_results, fallback_records = _run_mock_search_fallback(
            registry,
            query,
            subtask,
            filter_enabled,
            llm_call_log,
            round_index=round_index,
            section_id=section_id,
        )
        return fallback_results, [failed_record, *fallback_records]

    if tool_name == WEB_SEARCH_TOOL and not results:
        failed_record = ToolCallRecord(
            subtask_id=subtask.id,
            tool_name=tool_name,
            query=query,
            success=False,
            error=WEB_SEARCH_EMPTY_FALLBACK_ERROR,
            round_index=round_index,
            section_id=section_id,
        )
        fallback_results, fallback_records = _run_mock_search_fallback(
            registry,
            query,
            subtask,
            filter_enabled,
            llm_call_log,
            round_index=round_index,
            section_id=section_id,
        )
        return fallback_results, [failed_record, *fallback_records]

    kept_results, filtered_count = _process_tool_results(
        query, subtask, results, filter_enabled, llm_call_log
    )
    kept_results, cap_filtered_count = _cap_tool_results(kept_results)
    return kept_results, [
        ToolCallRecord(
            subtask_id=subtask.id,
            tool_name=tool_name,
            query=query,
            evidence_count=len(results),
            filtered_count=filtered_count + cap_filtered_count,
            round_index=round_index,
            section_id=section_id,
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
    *,
    round_index: int = 1,
    section_id: str | None = None,
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
                round_index=round_index,
                section_id=section_id,
            )
        ]

    kept_results, filtered_count = _process_tool_results(
        query, subtask, results, filter_enabled, llm_call_log
    )
    kept_results, cap_filtered_count = _cap_tool_results(kept_results)
    return kept_results, [
        ToolCallRecord(
            subtask_id=subtask.id,
            tool_name=MOCK_SEARCH_TOOL,
            query=query,
            evidence_count=len(results),
            filtered_count=filtered_count + cap_filtered_count,
            error=WEB_SEARCH_FALLBACK_NOTE,
            round_index=round_index,
            section_id=section_id,
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


def _cap_tool_results(evidence: list[Evidence]) -> tuple[list[Evidence], int]:
    capped = evidence[:MAX_EVIDENCE_PER_TOOL]
    return capped, max(0, len(evidence) - len(capped))


def _cap_evidence_pool(
    evidence: list[Evidence],
    section_plan: list[dict[str, object]],
) -> list[Evidence]:
    section_capped = _cap_evidence_by_section_budget(evidence, section_plan)
    evidence_budget = get_research_budgets().max_evidence_per_run
    return section_capped[:evidence_budget]


def _cap_evidence_by_section_budget(
    evidence: list[Evidence],
    section_plan: list[dict[str, object]],
) -> list[Evidence]:
    budgets = {
        str(section.get("section_id", "")): _section_budget(section)
        for section in section_plan
    }
    if not budgets:
        return evidence
    counts: dict[str, int] = {}
    capped: list[Evidence] = []
    for item in evidence:
        section_id = item.section_id
        budget = budgets.get(section_id or "")
        if budget is None:
            capped.append(item)
            continue
        current_count = counts.get(section_id or "", 0)
        if current_count >= budget:
            continue
        counts[section_id or ""] = current_count + 1
        capped.append(item)
    return capped


def _section_budget(section: dict[str, object]) -> int | None:
    value = section.get("budget")
    if isinstance(value, int) and value > 0:
        return value
    return None
