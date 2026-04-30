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

    assert evidence[0].claim_supported is None
    assert result == [
        {
            "claim": "Pricing",
            "evidence_ids": ["source-1"],
            "support_status": "supported",
            "claim_supported": True,
            "unsupported_reason": None,
            "supporting_snippets": [
                {
                    "evidence_id": "source-1",
                    "snippet": "Cursor pricing includes team plans.",
                    "source_url": "https://example.com",
                }
            ],
            "matched_terms": ["cursor", "includes", "plans", "pricing", "team"],
            "missing_terms": [],
            "support_score": 1.0,
        }
    ]


def test_validate_citation_support_marks_missing_evidence() -> None:
    finding = Finding(title="Pricing", summary="Missing support.", evidence_ids=["missing"])

    result = validate_citation_support([finding], [])

    assert result[0]["support_status"] == "unsupported"
    assert result[0]["claim_supported"] is False
    assert result[0]["unsupported_reason"] == "missing verified evidence"


def test_validate_citation_support_records_weak_snippet_support() -> None:
    evidence = [
        Evidence(
            id="source-1",
            subtask_id="collect",
            title="Source",
            source_url="https://example.com/source",
            snippet="Cursor pricing includes team plans.",
            verified=True,
        )
    ]
    finding = Finding(
        title="Security",
        summary="Copilot enterprise security includes audit logging.",
        evidence_ids=["source-1"],
    )

    result = validate_citation_support([finding], evidence)

    assert result[0]["support_status"] == "unsupported"
    assert result[0]["unsupported_reason"] == "snippet lacks lexical support"
    assert result[0]["supporting_snippets"] == [
        {
            "evidence_id": "source-1",
            "snippet": "Cursor pricing includes team plans.",
            "source_url": "https://example.com/source",
        }
    ]
    assert result[0]["matched_terms"] == ["includes"]
    assert result[0]["missing_terms"] == [
        "audit",
        "copilot",
        "enterprise",
        "logging",
        "security",
    ]
    assert result[0]["support_score"] == 0.17
