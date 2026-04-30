import json

from insight_graph.llm import ChatMessage
from insight_graph.state import Evidence, Finding

MIN_SUPPORT_SCORE = 0.5
FULL_SUPPORT_SCORE = 1.0


def validate_citation_support(
    findings: list[Finding],
    evidence_pool: list[Evidence],
    *,
    citation_judge_provider: str = "lexical",
    llm_client: object | None = None,
) -> list[dict[str, object]]:
    verified_by_id = {item.id: item for item in evidence_pool if item.verified}
    return [
        _support_record(
            finding,
            verified_by_id,
            citation_judge_provider=citation_judge_provider,
            llm_client=llm_client,
        )
        for finding in findings
    ]


def _support_record(
    finding: Finding,
    verified_by_id: dict[str, Evidence],
    *,
    citation_judge_provider: str,
    llm_client: object | None,
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
    lexical_status = _lexical_support_status(support["support_score"])
    record = {
        "claim": finding.title,
        "evidence_ids": supported_evidence,
        **support,
    }
    if citation_judge_provider == "llm" and llm_client is not None:
        return _apply_llm_judge(record, finding, evidence, llm_client)
    if lexical_status == "unsupported":
        return {
            "support_status": "unsupported",
            "claim_supported": False,
            "unsupported_reason": "snippet lacks lexical support",
            **record,
        }
    if lexical_status == "partial":
        return {
            "support_status": "partial",
            "claim_supported": False,
            "unsupported_reason": "partial lexical support",
            **record,
        }
    return {
        "support_status": "supported",
        "claim_supported": True,
        "unsupported_reason": None,
        **record,
    }


def _lexical_support_status(score: object) -> str:
    if not isinstance(score, int | float) or score < MIN_SUPPORT_SCORE:
        return "unsupported"
    if score < FULL_SUPPORT_SCORE:
        return "partial"
    return "supported"


def _apply_llm_judge(
    record: dict[str, object],
    finding: Finding,
    evidence: list[Evidence],
    llm_client: object,
) -> dict[str, object]:
    response = llm_client.complete_json(_build_citation_judge_messages(finding, evidence))
    parsed = json.loads(str(response))
    status = parsed.get("support_status") if isinstance(parsed, dict) else None
    reason = parsed.get("reason") if isinstance(parsed, dict) else None
    if status not in {"supported", "partial", "unsupported"}:
        status = _lexical_support_status(record.get("support_score"))
    reason_text = (
        reason if isinstance(reason, str) and reason.strip() else "LLM citation judge ran."
    )
    return {
        "support_status": status,
        "claim_supported": status == "supported",
        "unsupported_reason": None if status == "supported" else reason_text,
        "citation_judge": "llm",
        "citation_judge_reason": reason_text,
        **record,
    }


def _build_citation_judge_messages(
    finding: Finding,
    evidence: list[Evidence],
) -> list[ChatMessage]:
    snippets = "\n".join(
        f"- {item.id}: {item.snippet} ({item.source_url})" for item in evidence
    )
    return [
        ChatMessage(
            role="system",
            content=(
                "Judge whether the cited snippets support the claim. Return only JSON "
                "with support_status supported, partial, or unsupported, and reason."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Claim title: {finding.title}\n"
                f"Claim summary: {finding.summary}\n"
                f"Cited snippets:\n{snippets}"
            ),
        ),
    ]


def _snippet_support(summary: str, evidence: list[Evidence]) -> dict[str, object]:
    claim_terms = _meaningful_terms(summary)
    snippet_terms = set().union(*(_meaningful_terms(item.snippet) for item in evidence))
    matched_terms = sorted(claim_terms & snippet_terms)
    missing_terms = sorted(claim_terms - snippet_terms)
    support_score = round(len(matched_terms) / len(claim_terms), 2) if claim_terms else 0.0
    supporting_snippets = [_snippet_record(item, claim_terms) for item in evidence]
    supporting_snippets.sort(
        key=lambda item: (-float(item["support_score"]), str(item["evidence_id"]))
    )
    return {
        "supporting_snippets": supporting_snippets,
        "matched_terms": matched_terms,
        "missing_terms": missing_terms,
        "support_score": support_score,
    }


def _snippet_record(item: Evidence, claim_terms: set[str]) -> dict[str, object]:
    matched_terms = sorted(claim_terms & _meaningful_terms(item.snippet))
    support_score = round(len(matched_terms) / len(claim_terms), 2) if claim_terms else 0.0
    return {
        "evidence_id": item.id,
        "snippet": item.snippet,
        "source_url": item.source_url,
        "matched_terms": matched_terms,
        "support_score": support_score,
    }


def _sorted_terms(text: str) -> list[str]:
    return sorted(_meaningful_terms(text))


def _meaningful_terms(text: str) -> set[str]:
    return {term.lower().strip(".,;:()[]") for term in text.split() if len(term) > 3}
