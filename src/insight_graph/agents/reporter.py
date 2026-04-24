from insight_graph.state import GraphState


def write_report(state: GraphState) -> GraphState:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    reference_numbers = {item.id: index for index, item in enumerate(verified_evidence, start=1)}
    lines = [
        "# InsightGraph Research Report",
        "",
        f"**Research Request:** {state.user_request}",
        "",
        "## Key Findings",
        "",
    ]
    for finding in state.findings:
        citations = " ".join(
            f"[{reference_numbers[eid]}]"
            for eid in finding.evidence_ids
            if eid in reference_numbers
        )
        if not citations:
            continue
        lines.extend([f"### {finding.title}", "", f"{finding.summary} {citations}".strip(), ""])

    if state.critique is not None:
        lines.extend(["## Critic Assessment", "", state.critique.reason, ""])

    lines.extend(["## References", ""])
    for item in verified_evidence:
        number = reference_numbers[item.id]
        lines.append(f"[{number}] {item.title}. {item.source_url}")

    state.report_markdown = "\n".join(lines) + "\n"
    return state
