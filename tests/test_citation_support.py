from insight_graph.report_quality.citation_support import validate_citation_support
from insight_graph.state import Evidence, Finding


def test_validate_citation_support_marks_supported_claim() -> None:
    evidence = [
        Evidence(
            id="source-1",
            subtask_id="collect",
            title="Source",
            source_url="https://example.com",
            snippet="Cursor pricing includes team plans.",
            verified=True,
        )
    ]
    finding = Finding(
        title="Pricing",
        summary="Cursor pricing includes team plans.",
        evidence_ids=["source-1"],
    )

    result = validate_citation_support([finding], evidence)

    assert result == [
        {
            "claim": "Pricing",
            "evidence_ids": ["source-1"],
            "support_status": "supported",
            "unsupported_reason": None,
        }
    ]


def test_validate_citation_support_marks_missing_evidence() -> None:
    finding = Finding(title="Pricing", summary="Missing support.", evidence_ids=["missing"])

    result = validate_citation_support([finding], [])

    assert result[0]["support_status"] == "unsupported"
    assert result[0]["unsupported_reason"] == "missing verified evidence"
