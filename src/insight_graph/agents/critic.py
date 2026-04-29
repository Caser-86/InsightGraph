from insight_graph.report_quality.citation_support import validate_citation_support
from insight_graph.state import Critique, GraphState


def critique_analysis(state: GraphState) -> GraphState:
    state.citation_support = validate_citation_support(state.findings, state.evidence_pool)
    state.replan_requests = _build_replan_requests(state)
    verified_count = sum(1 for item in state.evidence_pool if item.verified)
    has_findings = bool(state.findings)
    verified_ids = {item.id for item in state.evidence_pool if item.verified}
    citations_supported = has_findings and all(
        any(evidence_id in verified_ids for evidence_id in finding.evidence_ids)
        for finding in state.findings
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
    for status in state.section_collection_status:
        if status.get("sufficient") is False:
            requests.append(
                {
                    "type": "missing_section_evidence",
                    "section_id": str(status.get("section_id", "")),
                    "missing_evidence": int(status.get("missing_evidence", 0)),
                    "missing_source_types": _missing_source_types(status),
                }
            )
    for item in state.citation_support:
        if item.get("support_status") == "unsupported":
            requests.append(
                {
                    "type": "unsupported_claim",
                    "claim": str(item.get("claim", "")),
                    "reason": str(item.get("unsupported_reason", "")),
                }
            )
    return requests


def _missing_source_types(status: dict[str, object]) -> list[str]:
    values = status.get("missing_source_types", [])
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str)]
