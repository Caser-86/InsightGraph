from typing import Any

from insight_graph.state import GraphState


def compress_conversation(
    state: GraphState,
    *,
    max_evidence: int = 5,
    max_tool_calls: int = 5,
) -> dict[str, Any]:
    evidence = state.evidence_pool[-max_evidence:] if max_evidence > 0 else []
    tool_calls = state.tool_call_log[-max_tool_calls:] if max_tool_calls > 0 else []
    return {
        "user_request": state.user_request,
        "evidence_count": len(state.evidence_pool),
        "finding_count": len(state.findings),
        "recent_evidence": [
            {
                "id": item.id,
                "title": item.title,
                "source_url": item.source_url,
                "source_type": item.source_type,
            }
            for item in evidence
        ],
        "tool_calls": [
            {
                "tool_name": record.tool_name,
                "success": record.success,
                "evidence_count": record.evidence_count,
                "filtered_count": record.filtered_count,
            }
            for record in tool_calls
        ],
        "findings": [
            {
                "title": finding.title,
                "summary": finding.summary,
                "evidence_ids": list(finding.evidence_ids),
            }
            for finding in state.findings
        ],
    }
