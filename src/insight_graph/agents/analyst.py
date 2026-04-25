import json
import os
import time

from insight_graph.llm import ChatCompletionClient, ChatMessage, get_llm_client, resolve_llm_config
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
)
from insight_graph.state import Evidence, Finding, GraphState


def get_analyst_provider(name: str | None = None) -> str:
    provider = name or os.getenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "deterministic")
    if provider not in {"deterministic", "llm"}:
        raise ValueError(f"Unknown analyst provider: {provider}")
    return provider


def analyze_evidence(
    state: GraphState,
    llm_client: ChatCompletionClient | None = None,
) -> GraphState:
    provider = get_analyst_provider()
    if provider == "deterministic":
        return _analyze_evidence_deterministic(state)

    try:
        return _analyze_evidence_with_llm(state, llm_client=llm_client)
    except ValueError:
        return _analyze_evidence_deterministic(state)


def _analyze_evidence_deterministic(state: GraphState) -> GraphState:
    evidence_ids = [item.id for item in state.evidence_pool]
    state.findings = [
        Finding(
            title="Official sources establish baseline product positioning",
            summary=(
                "Official pricing pages, documentation, and repositories provide the safest "
                "baseline for comparing product positioning and capabilities."
            ),
            evidence_ids=evidence_ids[:2],
        ),
        Finding(
            title="Open repositories add adoption and roadmap signals",
            summary=(
                "GitHub evidence helps evaluate public development activity, release cadence, "
                "and community-facing positioning."
            ),
            evidence_ids=evidence_ids[2:],
        ),
    ]
    return state


def _analyze_evidence_with_llm(
    state: GraphState,
    llm_client: ChatCompletionClient | None = None,
) -> GraphState:
    config = resolve_llm_config()
    if llm_client is None:
        if not config.api_key:
            raise ValueError("LLM api_key is required")
        llm_client = get_llm_client(config)

    messages = _build_analyst_messages(state)
    started = time.perf_counter()
    try:
        result = complete_json_with_observability(llm_client, messages)
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        state.llm_call_log.append(
            build_llm_call_record(
                stage="analyst",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=duration_ms,
                error=exc,
                secrets=[config.api_key],
            )
        )
        raise ValueError("LLM analyst failed.") from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    try:
        state.findings = _parse_analyst_findings(result.content, state.evidence_pool)
    except ValueError as exc:
        state.llm_call_log.append(
            build_llm_call_record(
                stage="analyst",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=duration_ms,
                error=exc,
                secrets=[config.api_key],
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
            )
        )
        raise

    state.llm_call_log.append(
        build_llm_call_record(
            stage="analyst",
            provider="llm",
            model=config.model,
            success=True,
            duration_ms=duration_ms,
            secrets=[config.api_key],
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
        )
    )
    return state


def _build_analyst_messages(state: GraphState) -> list[ChatMessage]:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    evidence_lines = []
    for item in verified_evidence:
        evidence_lines.append(
            "\n".join(
                [
                    f"- id: {item.id}",
                    f"  title: {item.title}",
                    f"  source_url: {item.source_url}",
                    f"  source_type: {item.source_type}",
                    f"  snippet: {item.snippet}",
                ]
            )
        )

    prompt = "\n\n".join(
        [
            f"User request: {state.user_request}",
            "Verified evidence:",
            "\n".join(evidence_lines),
            (
                "Return strict JSON with this shape only: "
                '{"findings": [{"title": "...", "summary": "...", '
                '"evidence_ids": ["verified-evidence-id"]}]} '
                "Every finding must cite one or more verified evidence IDs from the list."
            ),
        ]
    )

    return [
        ChatMessage(
            role="system",
            content=(
                "You are an analyst producing concise, evidence-grounded competitive "
                "research findings. Return JSON only."
            ),
        ),
        ChatMessage(role="user", content=prompt),
    ]


def _parse_analyst_findings(content: str | None, evidence_pool: list[Evidence]) -> list[Finding]:
    if not content:
        raise ValueError("LLM response content is required")

    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("LLM response must be valid JSON") from exc

    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")

    raw_findings = data.get("findings")
    if not isinstance(raw_findings, list) or not raw_findings:
        raise ValueError("LLM findings must be a non-empty list")

    verified_evidence_ids = {item.id for item in evidence_pool if item.verified}
    findings = []
    for raw_finding in raw_findings:
        if not isinstance(raw_finding, dict):
            raise ValueError("LLM finding must be an object")

        title = raw_finding.get("title")
        summary = raw_finding.get("summary")
        evidence_ids = raw_finding.get("evidence_ids")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("LLM finding title is required")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("LLM finding summary is required")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise ValueError("LLM finding evidence_ids must be a non-empty list")
        if not all(
            isinstance(evidence_id, str) and evidence_id.strip() for evidence_id in evidence_ids
        ):
            raise ValueError("LLM finding evidence_ids must be non-empty strings")
        if not set(evidence_ids).issubset(verified_evidence_ids):
            raise ValueError("LLM finding cites unverified or unknown evidence")

        findings.append(
            Finding(
                title=title.strip(),
                summary=summary.strip(),
                evidence_ids=evidence_ids,
            )
        )

    return findings
