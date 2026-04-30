from insight_graph.report_quality.citation_support import validate_citation_support
from insight_graph.state import Evidence, Finding


class FakeCitationJudgeClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages = []

    def complete_json(self, messages):
        self.messages = messages
        return self.content


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
                    "matched_terms": ["cursor", "includes", "plans", "pricing", "team"],
                    "support_score": 1.0,
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
            "matched_terms": ["includes"],
            "support_score": 0.17,
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


def test_validate_citation_support_marks_partial_claim() -> None:
    evidence = [
        Evidence(
            id="source-1",
            subtask_id="collect",
            title="Source",
            source_url="https://example.com/source",
            snippet="Copilot enterprise security includes encryption controls.",
            verified=True,
        )
    ]
    finding = Finding(
        title="Security",
        summary="Copilot enterprise security includes audit logging and encryption controls.",
        evidence_ids=["source-1"],
    )

    result = validate_citation_support([finding], evidence)

    assert result[0]["support_status"] == "partial"
    assert result[0]["claim_supported"] is False
    assert result[0]["unsupported_reason"] == "partial lexical support"
    assert result[0]["support_score"] == 0.75


def test_validate_citation_support_ranks_supporting_snippets_by_match_score() -> None:
    evidence = [
        Evidence(
            id="weak-source",
            subtask_id="collect",
            title="Weak Source",
            source_url="https://example.com/weak",
            snippet="Copilot pricing includes team plans.",
            verified=True,
        ),
        Evidence(
            id="strong-source",
            subtask_id="collect",
            title="Strong Source",
            source_url="https://example.com/strong",
            snippet="Copilot enterprise security includes audit logging.",
            verified=True,
        ),
    ]
    finding = Finding(
        title="Security",
        summary="Copilot enterprise security includes audit logging.",
        evidence_ids=["weak-source", "strong-source"],
    )

    result = validate_citation_support([finding], evidence)

    assert result[0]["supporting_snippets"] == [
        {
            "evidence_id": "strong-source",
            "snippet": "Copilot enterprise security includes audit logging.",
            "source_url": "https://example.com/strong",
            "matched_terms": ["audit", "copilot", "enterprise", "includes", "logging", "security"],
            "support_score": 1.0,
        },
        {
            "evidence_id": "weak-source",
            "snippet": "Copilot pricing includes team plans.",
            "source_url": "https://example.com/weak",
            "matched_terms": ["copilot", "includes"],
            "support_score": 0.33,
        },
    ]


def test_validate_citation_support_uses_optional_llm_judge() -> None:
    client = FakeCitationJudgeClient(
        '{"support_status": "supported", "reason": "LLM confirms claim support."}'
    )
    evidence = [
        Evidence(
            id="source-1",
            subtask_id="collect",
            title="Source",
            source_url="https://example.com/source",
            snippet="Copilot enterprise security includes encryption controls.",
            verified=True,
        )
    ]
    finding = Finding(
        title="Security",
        summary="Copilot enterprise security includes audit logging and encryption controls.",
        evidence_ids=["source-1"],
    )

    result = validate_citation_support(
        [finding],
        evidence,
        citation_judge_provider="llm",
        llm_client=client,
    )

    assert result[0]["support_status"] == "supported"
    assert result[0]["claim_supported"] is True
    assert result[0]["unsupported_reason"] is None
    assert result[0]["citation_judge"] == "llm"
    assert result[0]["citation_judge_reason"] == "LLM confirms claim support."
    assert "audit logging" in client.messages[1].content
