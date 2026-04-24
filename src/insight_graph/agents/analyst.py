from insight_graph.state import Finding, GraphState


def analyze_evidence(state: GraphState) -> GraphState:
    evidence_ids = [item.id for item in state.evidence_pool]
    state.findings = [
        Finding(
            title="Official sources establish baseline product positioning",
            summary=(
                "Official pricing pages, documentation, and repositories provide the safest "
                "baseline for comparing product positioning and capabilities."
            ),
            evidence_ids=evidence_ids[:2],
        ),
        Finding(
            title="Open repositories add adoption and roadmap signals",
            summary=(
                "GitHub evidence helps evaluate public development activity, release cadence, "
                "and community-facing positioning."
            ),
            evidence_ids=evidence_ids[2:],
        ),
    ]
    return state
