from __future__ import annotations

from typing import Any

from insight_graph.state import GraphState


def build_fact_conclusion_mapping(state: GraphState) -> dict[str, Any]:
    verified_ids = {item.id for item in state.evidence_pool if item.verified}
    records: list[dict[str, Any]] = []

    for finding in state.findings:
        records.append(
            _mapping_record(
                claim=finding.title,
                evidence_ids=finding.evidence_ids,
                verified_ids=verified_ids,
                claim_type="finding",
            )
        )

    for row in state.competitive_matrix:
        records.append(
            _mapping_record(
                claim=f"{row.product}: {row.positioning}",
                evidence_ids=row.evidence_ids,
                verified_ids=verified_ids,
                claim_type="competitive_matrix",
            )
        )

    for claim in state.grounded_claims:
        claim_text = claim.get("claim")
        evidence_ids = claim.get("evidence_ids", [])
        if not isinstance(claim_text, str) or not claim_text.strip():
            continue
        if not isinstance(evidence_ids, list):
            evidence_ids = []
        records.append(
            _mapping_record(
                claim=claim_text.strip(),
                evidence_ids=[item for item in evidence_ids if isinstance(item, str)],
                verified_ids=verified_ids,
                claim_type="grounded_claim",
            )
        )

    total = len(records)
    mapped = sum(1 for item in records if item["mapped"] is True)
    weak = [item for item in records if item["mapped"] is False]
    score = 100 if total == 0 else round(mapped / total * 100)
    return {
        "conclusion_count": total,
        "mapped_conclusion_count": mapped,
        "weak_conclusion_count": len(weak),
        "mapping_score": score,
        "weak_conclusions": weak,
    }


def _mapping_record(
    *,
    claim: str,
    evidence_ids: list[str],
    verified_ids: set[str],
    claim_type: str,
) -> dict[str, Any]:
    resolved_ids = [evidence_id for evidence_id in evidence_ids if evidence_id in verified_ids]
    mapped = bool(evidence_ids) and len(resolved_ids) == len(evidence_ids)
    return {
        "claim": claim,
        "claim_type": claim_type,
        "evidence_ids": evidence_ids,
        "mapped_evidence_ids": resolved_ids,
        "mapped": mapped,
    }
