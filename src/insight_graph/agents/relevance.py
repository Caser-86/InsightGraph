import os
from typing import Protocol

from pydantic import BaseModel

from insight_graph.state import Evidence, Subtask


class EvidenceRelevanceDecision(BaseModel):
    evidence_id: str
    relevant: bool
    reason: str


class RelevanceJudge(Protocol):
    def judge(
        self,
        query: str,
        subtask: Subtask,
        evidence: Evidence,
    ) -> EvidenceRelevanceDecision: ...


class DeterministicRelevanceJudge:
    def judge(
        self,
        query: str,
        subtask: Subtask,
        evidence: Evidence,
    ) -> EvidenceRelevanceDecision:
        if not evidence.verified:
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="Evidence is not verified.",
            )
        if not evidence.title.strip():
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="Evidence title is empty.",
            )
        if not evidence.source_url.strip():
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="Evidence source URL is empty.",
            )
        if not evidence.snippet.strip():
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="Evidence snippet is empty.",
            )
        return EvidenceRelevanceDecision(
            evidence_id=evidence.id,
            relevant=True,
            reason="Evidence is verified and has required content.",
        )


def is_relevance_filter_enabled() -> bool:
    value = os.getenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "").lower()
    return value in {"1", "true", "yes"}


def get_relevance_judge(name: str | None = None) -> RelevanceJudge:
    judge_name = (name or os.getenv("INSIGHT_GRAPH_RELEVANCE_JUDGE", "deterministic")).lower()
    if judge_name == "deterministic":
        return DeterministicRelevanceJudge()
    raise ValueError(f"Unknown relevance judge: {judge_name}")


def filter_relevant_evidence(
    query: str,
    subtask: Subtask,
    evidence: list[Evidence],
    judge: RelevanceJudge | None = None,
) -> tuple[list[Evidence], int]:
    active_judge = judge or get_relevance_judge()
    kept: list[Evidence] = []
    filtered_count = 0
    for item in evidence:
        decision = active_judge.judge(query, subtask, item)
        if decision.relevant:
            kept.append(item)
        else:
            filtered_count += 1
    return kept, filtered_count
