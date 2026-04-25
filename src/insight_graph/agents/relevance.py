import json
import os
from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel

from insight_graph.llm.client import (
    ChatCompletionClient,
    ChatMessage,
    OpenAICompatibleChatClient,
)
from insight_graph.llm.config import resolve_llm_config
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


class OpenAICompatibleRelevanceJudge:
    def __init__(
        self,
        client: ChatCompletionClient | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        client_factory: Callable[..., object] | None = None,
    ) -> None:
        config = resolve_llm_config(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        self._config = config
        self._client = client or OpenAICompatibleChatClient(
            config=config,
            client_factory=client_factory,
        )

    def judge(
        self,
        query: str,
        subtask: Subtask,
        evidence: Evidence,
    ) -> EvidenceRelevanceDecision:
        if not self._config.api_key:
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="OpenAI-compatible relevance judge is missing an API key.",
            )

        try:
            content = self._client.complete_json(
                _build_relevance_messages(query, subtask, evidence)
            )
            return _parse_relevance_json(content, evidence.id)
        except ValueError:
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="OpenAI-compatible relevance judge returned invalid JSON.",
            )
        except Exception as exc:
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason=f"OpenAI-compatible relevance judge failed: {exc}",
            )

def _build_relevance_messages(
    query: str,
    subtask: Subtask,
    evidence: Evidence,
) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="system",
            content=(
                "You judge whether evidence is relevant to a research query and subtask. "
                "Return only JSON with boolean field relevant and string field reason."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Query: {query}\n"
                f"Subtask ID: {subtask.id}\n"
                f"Subtask description: {subtask.description}\n"
                f"Evidence ID: {evidence.id}\n"
                f"Evidence title: {evidence.title}\n"
                f"Evidence source URL: {evidence.source_url}\n"
                f"Evidence verified: {evidence.verified}\n"
                f"Evidence snippet: {evidence.snippet}"
            ),
        ),
    ]


def _parse_relevance_json(content: str | None, evidence_id: str) -> EvidenceRelevanceDecision:
    if not content:
        raise ValueError("OpenAI-compatible relevance judge returned empty content.")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("OpenAI-compatible relevance judge returned non-object JSON.")
    relevant = parsed.get("relevant")
    if not isinstance(relevant, bool):
        raise ValueError("OpenAI-compatible relevance judge returned invalid relevant field.")
    reason = parsed.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = "OpenAI-compatible relevance judge returned a decision."
    return EvidenceRelevanceDecision(
        evidence_id=evidence_id,
        relevant=relevant,
        reason=reason,
    )


def is_relevance_filter_enabled() -> bool:
    value = os.getenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "").lower()
    return value in {"1", "true", "yes"}


def get_relevance_judge(name: str | None = None) -> RelevanceJudge:
    judge_name = (name or os.getenv("INSIGHT_GRAPH_RELEVANCE_JUDGE", "deterministic")).lower()
    if judge_name == "deterministic":
        return DeterministicRelevanceJudge()
    if judge_name == "openai_compatible":
        return OpenAICompatibleRelevanceJudge()
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
