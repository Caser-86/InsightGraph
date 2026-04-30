from insight_graph.report_quality.citation_support import validate_citation_support
from insight_graph.state import Critique, GraphState


def critique_analysis(state: GraphState) -> GraphState:
    state.citation_support = validate_citation_support(state.findings, state.evidence_pool)
    state.replan_requests = _build_replan_requests(state)
    state.tried_strategies = _updated_tried_strategies(
        state.tried_strategies,
        state.replan_requests,
    )
    verified_count = sum(1 for item in state.evidence_pool if item.verified)
    has_findings = bool(state.findings)
    citations_supported = has_findings and all(
        item.get("support_status") == "supported" for item in state.citation_support
    )
    passed = verified_count >= 3 and has_findings and citations_supported
    missing_topics = []
    if verified_count < 3:
        missing_topics.append("verified evidence")
    if not has_findings:
        missing_topics.append("analysis findings")
    if not citations_supported:
        missing_topics.append("citation support")
    state.critique = Critique(
        passed=passed,
        reason=(
            "Sufficient verified evidence and findings are available."
            if passed
            else "Evidence, findings, or citation support are insufficient."
        ),
        missing_topics=missing_topics,
    )
    return state


def _build_replan_requests(state: GraphState) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []
    tried_strategies = set(state.tried_strategies)
    for status in state.section_collection_status:
        if status.get("sufficient") is False:
            section_id = str(status.get("section_id", ""))
            missing_source_types = _missing_source_types(status)
            strategy_key = _missing_section_strategy_key(section_id, missing_source_types)
            if strategy_key in tried_strategies:
                continue
            requests.append(
                {
                    "type": "missing_section_evidence",
                    "section_id": section_id,
                    "missing_evidence": int(status.get("missing_evidence", 0)),
                    "missing_source_types": missing_source_types,
                    "strategy_key": strategy_key,
                }
            )
    for item in state.citation_support:
        if item.get("support_status") != "supported":
            requests.append(
                {
                    "type": "unsupported_claim",
                    "claim": str(item.get("claim", "")),
                    "reason": str(item.get("unsupported_reason", "")),
                }
            )
    return requests


def _missing_section_strategy_key(section_id: str, missing_source_types: list[str]) -> str:
    source_key = ",".join(sorted(missing_source_types)) if missing_source_types else "evidence"
    return f"missing_section_evidence:{section_id}:{source_key}"


def _updated_tried_strategies(
    existing: list[str],
    replan_requests: list[dict[str, object]],
) -> list[str]:
    strategies = list(existing)
    seen = set(strategies)
    for request in replan_requests:
        strategy_key = request.get("strategy_key")
        if not isinstance(strategy_key, str) or not strategy_key or strategy_key in seen:
            continue
        seen.add(strategy_key)
        strategies.append(strategy_key)
    return strategies


def _missing_source_types(status: dict[str, object]) -> list[str]:
    values = status.get("missing_source_types", [])
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str)]
