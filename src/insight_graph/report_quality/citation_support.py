from insight_graph.state import Evidence, Finding

MIN_SUPPORT_SCORE = 0.5


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
            "claim_supported": False,
            "unsupported_reason": "missing verified evidence",
            "supporting_snippets": [],
            "matched_terms": [],
            "missing_terms": _sorted_terms(finding.summary),
            "support_score": 0.0,
        }
    evidence = [verified_by_id[item] for item in supported_evidence]
    support = _snippet_support(finding.summary, evidence)
    if support["support_score"] < MIN_SUPPORT_SCORE:
        return {
            "claim": finding.title,
            "evidence_ids": supported_evidence,
            "support_status": "unsupported",
            "claim_supported": False,
            "unsupported_reason": "snippet lacks lexical support",
            **support,
        }
    return {
        "claim": finding.title,
        "evidence_ids": supported_evidence,
        "support_status": "supported",
        "claim_supported": True,
        "unsupported_reason": None,
        **support,
    }


def _snippet_support(summary: str, evidence: list[Evidence]) -> dict[str, object]:
    claim_terms = _meaningful_terms(summary)
    snippet_terms = set().union(*(_meaningful_terms(item.snippet) for item in evidence))
    matched_terms = sorted(claim_terms & snippet_terms)
    missing_terms = sorted(claim_terms - snippet_terms)
    support_score = round(len(matched_terms) / len(claim_terms), 2) if claim_terms else 0.0
    return {
        "supporting_snippets": [
            {
                "evidence_id": item.id,
                "snippet": item.snippet,
                "source_url": item.source_url,
            }
            for item in evidence
        ],
        "matched_terms": matched_terms,
        "missing_terms": missing_terms,
        "support_score": support_score,
    }


def _sorted_terms(text: str) -> list[str]:
    return sorted(_meaningful_terms(text))


def _meaningful_terms(text: str) -> set[str]:
    return {term.lower().strip(".,;:()[]") for term in text.split() if len(term) > 3}
