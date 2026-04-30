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
                    "missing_section": section_id,
                    "missing_evidence": int(status.get("missing_evidence", 0)),
                    "missing_source_types": missing_source_types,
                    "strategy_key": strategy_key,
                }
            )
    for item in state.citation_support:
        if item.get("support_status") != "supported":
            requests.append(_unsupported_claim_request(state, item))
    return requests


def _unsupported_claim_request(
    state: GraphState,
    item: dict[str, object],
) -> dict[str, object]:
    claim = str(item.get("claim", ""))
    request: dict[str, object] = {
        "type": "unsupported_claim",
        "claim": claim,
        "reason": str(item.get("unsupported_reason", "")),
    }
    evidence = _first_supported_evidence(state, item)
    if evidence is not None:
        if evidence.section_id:
            request["missing_section"] = evidence.section_id
        request["missing_source_type"] = evidence.source_type
    missing_entity = _first_entity_name(state)
    if missing_entity:
        request["missing_entity"] = missing_entity
    if claim:
        request["unsupported_claim_hint"] = claim
    return request


def _first_supported_evidence(state: GraphState, item: dict[str, object]):
    evidence_ids = item.get("evidence_ids", [])
    if not isinstance(evidence_ids, list):
        return None
    evidence_by_id = {evidence.id: evidence for evidence in state.evidence_pool}
    for evidence_id in evidence_ids:
        if not isinstance(evidence_id, str):
            continue
        evidence = evidence_by_id.get(evidence_id)
        if evidence is not None:
            return evidence
    return None


def _first_entity_name(state: GraphState) -> str:
    for entity in state.resolved_entities:
        name = entity.get("name")
        if isinstance(name, str) and name:
            return name
    return ""


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
