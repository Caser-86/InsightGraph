from insight_graph.state import Critique, GraphState


def critique_analysis(state: GraphState) -> GraphState:
    verified_count = sum(1 for item in state.evidence_pool if item.verified)
    has_findings = bool(state.findings)
    passed = verified_count >= 3 and has_findings
    state.critique = Critique(
        passed=passed,
        reason=(
            "Sufficient verified evidence and findings are available."
            if passed
            else "Evidence or findings are insufficient."
        ),
        missing_topics=[] if passed else ["verified evidence", "analysis findings"],
    )
    return state
