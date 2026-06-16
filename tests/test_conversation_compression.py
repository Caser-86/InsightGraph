from insight_graph.report_quality.conversation_compression import compress_conversation
from insight_graph.state import Evidence, Finding, GraphState, ToolCallRecord


def test_compress_conversation_preserves_recent_evidence_and_tool_summary() -> None:
    state = GraphState(
        user_request="Compare vendors",
        evidence_pool=[
            Evidence(
                id="ev-1",
                subtask_id="collect",
                title="Official roadmap",
                source_url="https://example.com/roadmap",
                snippet="Official product roadmap evidence with enough detail.",
                source_type="official_site",
                verified=True,
            ),
            Evidence(
                id="ev-2",
                subtask_id="collect",
                title="Market signal",
                source_url="https://example.com/news",
                snippet="Recent market signal evidence with enough detail.",
                source_type="news",
                verified=True,
            ),
        ],
        tool_call_log=[
            ToolCallRecord(
                subtask_id="collect",
                tool_name="web_search",
                query="vendors",
                evidence_count=2,
                filtered_count=0,
                success=True,
            )
        ],
    )

    summary = compress_conversation(state, max_evidence=1)

    assert summary["user_request"] == "Compare vendors"
    assert summary["evidence_count"] == 2
    assert summary["recent_evidence"] == [
        {
            "id": "ev-2",
            "title": "Market signal",
            "source_url": "https://example.com/news",
            "source_type": "news",
        }
    ]
    assert summary["tool_calls"] == [
        {
            "tool_name": "web_search",
            "success": True,
            "evidence_count": 2,
            "filtered_count": 0,
        }
    ]


def test_compress_conversation_preserves_findings_with_citations() -> None:
    state = GraphState(
        user_request="Assess vendor",
        findings=[
            Finding(
                title="Roadmap signals",
                summary="Vendor has strong official roadmap signals.",
                evidence_ids=["ev-1"],
            )
        ],
    )

    summary = compress_conversation(state)

    assert summary["findings"] == [
        {
            "title": "Roadmap signals",
            "summary": "Vendor has strong official roadmap signals.",
            "evidence_ids": ["ev-1"],
        }
    ]
