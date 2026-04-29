import json
import os
import time
from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel

from insight_graph.llm.client import (
    ChatCompletionClient,
    ChatCompletionResult,
    ChatMessage,
    OpenAICompatibleChatClient,
)
from insight_graph.llm.config import resolve_llm_config
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
    get_llm_wire_api,
)
from insight_graph.report_quality.budgeting import can_start_llm_call_from_records
from insight_graph.state import Evidence, LLMCallRecord, Subtask


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
        llm_call_log: list[LLMCallRecord] | None = None,
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
        self._llm_call_log = llm_call_log

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
        if self._llm_call_log is not None and not can_start_llm_call_from_records(
            self._llm_call_log
        ):
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="LLM token budget exhausted.",
            )

        started = time.perf_counter()
        try:
            result = complete_json_with_observability(
                self._client,
                _build_relevance_messages(query, subtask, evidence),
            )
        except ValueError as exc:
            self._record_llm_call(False, started, exc)
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="OpenAI-compatible relevance judge returned invalid JSON.",
            )
        except Exception as exc:
            self._record_llm_call(False, started, exc)
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason=f"OpenAI-compatible relevance judge failed: {exc}",
            )

        try:
            decision = _parse_relevance_json(result.content, evidence.id)
        except ValueError as exc:
            self._record_llm_call(False, started, exc, result=result)
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="OpenAI-compatible relevance judge returned invalid JSON.",
            )

        self._record_llm_call(True, started, result=result)
        return decision

    def _record_llm_call(
        self,
        success: bool,
        started: float,
        error: Exception | None = None,
        result: ChatCompletionResult | None = None,
    ) -> None:
        if self._llm_call_log is None:
            return
        duration_ms = int((time.perf_counter() - started) * 1000)
        self._llm_call_log.append(
            build_llm_call_record(
                stage="relevance",
                provider="openai_compatible",
                model=self._config.model,
                success=success,
                duration_ms=duration_ms,
                wire_api=get_llm_wire_api(self._client),
                error=error,
                secrets=[self._config.api_key],
                input_tokens=result.input_tokens if result is not None else None,
                output_tokens=result.output_tokens if result is not None else None,
                total_tokens=result.total_tokens if result is not None else None,
            )
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


def get_relevance_judge(
    name: str | None = None,
    llm_call_log: list[LLMCallRecord] | None = None,
) -> RelevanceJudge:
    judge_name = (name or os.getenv("INSIGHT_GRAPH_RELEVANCE_JUDGE", "deterministic")).lower()
    if judge_name == "deterministic":
        return DeterministicRelevanceJudge()
    if judge_name == "openai_compatible":
        return OpenAICompatibleRelevanceJudge(llm_call_log=llm_call_log)
    raise ValueError(f"Unknown relevance judge: {judge_name}")


def filter_relevant_evidence(
    query: str,
    subtask: Subtask,
    evidence: list[Evidence],
    judge: RelevanceJudge | None = None,
    llm_call_log: list[LLMCallRecord] | None = None,
) -> tuple[list[Evidence], int]:
    active_judge = judge or get_relevance_judge(llm_call_log=llm_call_log)
    kept: list[Evidence] = []
    filtered_count = 0
    for item in evidence:
        decision = active_judge.judge(query, subtask, item)
        if decision.relevant:
            kept.append(item)
        else:
            filtered_count += 1
    return kept, filtered_count
