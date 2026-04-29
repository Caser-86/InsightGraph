from insight_graph.state import Evidence, Finding


def validate_citation_support(
    findings: list[Finding],
    evidence_pool: list[Evidence],
) -> list[dict[str, object]]:
    verified_by_id = {item.id: item for item in evidence_pool if item.verified}
    return [_support_record(finding, verified_by_id) for finding in findings]


def _support_record(
    finding: Finding,
    verified_by_id: dict[str, Evidence],
) -> dict[str, object]:
    supported_evidence = [
        evidence_id for evidence_id in finding.evidence_ids if evidence_id in verified_by_id
    ]
    if not supported_evidence:
        return {
            "claim": finding.title,
            "evidence_ids": list(finding.evidence_ids),
            "support_status": "unsupported",
            "unsupported_reason": "missing verified evidence",
        }
    evidence = [verified_by_id[item] for item in supported_evidence]
    if not _has_lexical_overlap(finding.summary, evidence):
        return {
            "claim": finding.title,
            "evidence_ids": supported_evidence,
            "support_status": "unsupported",
            "unsupported_reason": "snippet lacks lexical support",
        }
    return {
        "claim": finding.title,
        "evidence_ids": supported_evidence,
        "support_status": "supported",
        "unsupported_reason": None,
    }


def _has_lexical_overlap(summary: str, evidence: list[Evidence]) -> bool:
    claim_terms = _meaningful_terms(summary)
    snippet_terms = set().union(*(_meaningful_terms(item.snippet) for item in evidence))
    return bool(claim_terms & snippet_terms)


def _meaningful_terms(text: str) -> set[str]:
    return {term.lower().strip(".,;:()[]") for term in text.split() if len(term) > 3}
