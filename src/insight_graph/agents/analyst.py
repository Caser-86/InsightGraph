import json
import os
import re
import time

from insight_graph.llm import ChatCompletionClient, ChatMessage, get_llm_client, resolve_llm_config
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
    get_llm_wire_api,
)
from insight_graph.llm.trace_writer import write_full_llm_trace_event
from insight_graph.report_quality.budgeting import can_start_llm_call
from insight_graph.state import CompetitiveMatrixRow, Evidence, Finding, GraphState

PRODUCT_ALIASES = {
    "Cursor": ["cursor"],
    "OpenCode": ["opencode", "open code"],
    "Claude Code": ["claude code"],
    "GitHub Copilot": ["github copilot"],
    "Codeium": ["codeium"],
    "Windsurf": ["windsurf"],
}

SOURCE_POSITIONING = {
    "github": "Open-source or developer ecosystem signal",
    "docs": "Documented product or local research source",
    "news": "Market/news activity signal",
    "official_site": "Official product positioning signal",
}

SOURCE_STRENGTHS = {
    "official_site": "Official/documented source coverage",
    "docs": "Official/documented source coverage",
    "github": "Repository or developer ecosystem evidence",
    "news": "News or launch activity evidence",
}


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
    if not can_start_llm_call(state):
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
                "Cursor publishes product tiers and pricing on its official pricing page. "
                "GitHub Copilot documentation describes IDE integrations and enterprise features."
            ),
            evidence_ids=evidence_ids[:2],
        ),
        Finding(
            title="Open repositories add adoption and roadmap signals",
            summary=(
                "The OpenCode repository provides public project information, README content, "
                "and release history."
            ),
            evidence_ids=evidence_ids[2:],
        ),
    ]
    state.competitive_matrix = build_competitive_matrix(
        state.user_request,
        state.evidence_pool,
    )
    return state


def build_competitive_matrix(
    user_request: str,
    evidence_pool: list[Evidence],
) -> list[CompetitiveMatrixRow]:
    verified_evidence = [item for item in evidence_pool if item.verified]
    if not verified_evidence:
        return []

    rows = []
    for product, aliases in PRODUCT_ALIASES.items():
        product_evidence = [
            item for item in verified_evidence if _mentions_product(user_request, item, aliases)
        ]
        if not product_evidence:
            continue
        rows.append(_build_matrix_row(product, product_evidence[:3]))

    if rows:
        return rows
    return [_build_matrix_row("General market evidence", verified_evidence[:3])]


def _mentions_product(user_request: str, evidence: Evidence, aliases: list[str]) -> bool:
    del user_request
    evidence_haystack = " ".join([evidence.title, evidence.source_url, evidence.snippet])
    return any(_matches_product_alias(evidence_haystack, alias) for alias in aliases)


def _matches_product_alias(haystack: str, alias: str) -> bool:
    if alias == "open code":
        return False
    return _matches_alias(haystack, alias)


def _matches_alias(haystack: str, alias: str) -> bool:
    pattern = r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])"
    return re.search(pattern, haystack, flags=re.IGNORECASE) is not None


def _build_matrix_row(product: str, evidence: list[Evidence]) -> CompetitiveMatrixRow:
    source_types = [item.source_type for item in evidence]
    positioning = _positioning_for_sources(source_types)
    strengths = _strengths_for_sources(source_types)
    return CompetitiveMatrixRow(
        product=product,
        positioning=positioning,
        strengths=strengths,
        evidence_ids=[item.id for item in evidence],
    )


def _positioning_for_sources(source_types: list[str]) -> str:
    for source_type in ("github", "docs", "news", "official_site"):
        if source_type in source_types:
            return SOURCE_POSITIONING[source_type]
    return "Evidence-backed product signal"


def _strengths_for_sources(source_types: list[str]) -> list[str]:
    strengths = []
    for source_type in ("official_site", "docs", "github", "news"):
        strength = SOURCE_STRENGTHS.get(source_type)
        if source_type in source_types and strength and strength not in strengths:
            strengths.append(strength)
    if not strengths:
        strengths.append("Verified evidence available")
    return strengths[:3]


def _analyze_evidence_with_llm(
    state: GraphState,
    llm_client: ChatCompletionClient | None = None,
) -> GraphState:
    config = resolve_llm_config()
    messages = _build_analyst_messages(state)
    if llm_client is None:
        if not config.api_key:
            raise ValueError("LLM api_key is required")
        llm_client = get_llm_client(config, purpose="analyst", messages=messages)

    wire_api = get_llm_wire_api(llm_client)
    started = time.perf_counter()
    try:
        result = complete_json_with_observability(llm_client, messages)
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        state.llm_call_log.append(
            build_llm_call_record(
                stage="analyst",
                provider="llm",
                model=getattr(getattr(llm_client, "config", None), "model", config.model),
                success=False,
                duration_ms=duration_ms,
                wire_api=wire_api,
                error=exc,
                secrets=[config.api_key],
                llm_client=llm_client,
            )
        )
        write_full_llm_trace_event(
            stage="analyst",
            llm_client=llm_client,
            messages=messages,
            output_text="",
            duration_ms=duration_ms,
            success=False,
            error=exc,
        )
        raise ValueError("LLM analyst failed.") from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    try:
        state.findings, parsed_matrix = _parse_analyst_response(
            result.content,
            state.evidence_pool,
        )
        if parsed_matrix is None:
            parsed_matrix = build_competitive_matrix(
                state.user_request,
                state.evidence_pool,
            )
        state.competitive_matrix = parsed_matrix
    except ValueError as exc:
        state.llm_call_log.append(
            build_llm_call_record(
                stage="analyst",
                provider="llm",
                model=getattr(getattr(llm_client, "config", None), "model", config.model),
                success=False,
                duration_ms=duration_ms,
                wire_api=wire_api,
                error=exc,
                secrets=[config.api_key],
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                llm_client=llm_client,
            )
        )
        write_full_llm_trace_event(
            stage="analyst",
            llm_client=llm_client,
            messages=messages,
            output_text=result.content or "",
            duration_ms=duration_ms,
            success=False,
            error=exc,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
        )
        raise

    state.llm_call_log.append(
        build_llm_call_record(
            stage="analyst",
            provider="llm",
            model=getattr(getattr(llm_client, "config", None), "model", config.model),
            success=True,
            duration_ms=duration_ms,
            wire_api=wire_api,
            secrets=[config.api_key],
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            llm_client=llm_client,
        )
    )
    write_full_llm_trace_event(
        stage="analyst",
        llm_client=llm_client,
        messages=messages,
        output_text=result.content or "",
        duration_ms=duration_ms,
        success=True,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
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
                '"evidence_ids": ["verified-evidence-id"]}], '
                '"competitive_matrix": [{"product": "...", '
                '"positioning": "...", "strengths": ["..."], '
                '"evidence_ids": ["verified-evidence-id"]}]} '
                "competitive_matrix is optional, but each matrix row must include "
                "product, positioning, strengths, and evidence_ids that cite "
                "verified evidence IDs from the list. Every finding must cite "
                "one or more verified evidence IDs from the list."
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


def _parse_analyst_response(
    content: str | None,
    evidence_pool: list[Evidence],
) -> tuple[list[Finding], list[CompetitiveMatrixRow] | None]:
    data = _load_analyst_json(content)
    findings = _parse_analyst_findings_from_data(data, evidence_pool)
    matrix = _parse_competitive_matrix_from_data(data, evidence_pool)
    return findings, matrix


def _load_analyst_json(content: str | None) -> dict:
    if not content:
        raise ValueError("LLM response content is required")

    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("LLM response must be valid JSON") from exc

    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")

    return data


def _parse_analyst_findings(content: str | None, evidence_pool: list[Evidence]) -> list[Finding]:
    data = _load_analyst_json(content)
    return _parse_analyst_findings_from_data(data, evidence_pool)


def _parse_analyst_findings_from_data(data: dict, evidence_pool: list[Evidence]) -> list[Finding]:
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


def _parse_competitive_matrix_from_data(
    data: dict,
    evidence_pool: list[Evidence],
) -> list[CompetitiveMatrixRow] | None:
    if "competitive_matrix" not in data:
        return None
    raw_matrix = data.get("competitive_matrix")
    if not isinstance(raw_matrix, list):
        raise ValueError("LLM competitive_matrix must be a list")

    verified_evidence_ids = {item.id for item in evidence_pool if item.verified}
    matrix = []
    for raw_row in raw_matrix:
        if not isinstance(raw_row, dict):
            raise ValueError("LLM competitive_matrix row must be an object")

        product = raw_row.get("product")
        positioning = raw_row.get("positioning")
        strengths = raw_row.get("strengths")
        evidence_ids = raw_row.get("evidence_ids")
        if not isinstance(product, str) or not product.strip():
            raise ValueError("LLM competitive_matrix product is required")
        if not isinstance(positioning, str) or not positioning.strip():
            raise ValueError("LLM competitive_matrix positioning is required")
        if not isinstance(strengths, list) or not all(
            isinstance(item, str) and item.strip() for item in strengths
        ):
            raise ValueError("LLM competitive_matrix strengths must be strings")
        if len(strengths) > 5:
            raise ValueError("LLM competitive_matrix strengths must have at most 5 items")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise ValueError("LLM competitive_matrix evidence_ids are required")
        if not all(
            isinstance(evidence_id, str) and evidence_id.strip() for evidence_id in evidence_ids
        ):
            raise ValueError("LLM competitive_matrix evidence_ids must be strings")
        if not set(evidence_ids).issubset(verified_evidence_ids):
            raise ValueError("LLM competitive_matrix cites unverified or unknown evidence")

        matrix.append(
            CompetitiveMatrixRow(
                product=product.strip(),
                positioning=positioning.strip(),
                strengths=[item.strip() for item in strengths],
                evidence_ids=evidence_ids,
            )
        )
    return matrix
