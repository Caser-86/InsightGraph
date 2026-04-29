from insight_graph.report_quality.citation_support import validate_citation_support
from insight_graph.state import Critique, GraphState


def critique_analysis(state: GraphState) -> GraphState:
    state.citation_support = validate_citation_support(state.findings, state.evidence_pool)
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
