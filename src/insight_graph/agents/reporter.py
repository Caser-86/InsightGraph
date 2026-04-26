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
from insight_graph.state import CompetitiveMatrixRow, Evidence, GraphState

CITATION_PATTERN = re.compile(r"\[(\d+)]")
REFERENCE_HEADING_PATTERN = re.compile(
    r"^ {0,3}#+\s*(references|sources)\b.*\Z", re.IGNORECASE | re.MULTILINE | re.DOTALL
)
RESIDUAL_REFERENCE_HEADING_PATTERN = re.compile(
    r"^ {0,3}#+\s*(references|sources)\b", re.IGNORECASE | re.MULTILINE
)
KEY_FINDINGS_HEADING_PATTERN = re.compile(r"(?im)^##\s+Key Findings\s*$")
COMPETITIVE_MATRIX_HEADING_PATTERN = re.compile(
    r"(?im)^ {0,3}#{2,6}\s+Competitive Matrix\s*#*\s*$"
)
NEXT_SECTION_HEADING_PATTERN = re.compile(r"(?m)^ {0,3}##\s+")
SMART_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
    }
)


class ReporterFallbackError(ValueError):
    pass


def get_reporter_provider(name: str | None = None) -> str:
    provider = name or os.getenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "deterministic")
    if provider not in {"deterministic", "llm"}:
        raise ValueError(f"Unknown reporter provider: {provider}")
    return provider


def write_report(
    state: GraphState,
    llm_client: ChatCompletionClient | None = None,
) -> GraphState:
    provider = get_reporter_provider()
    if provider == "deterministic":
        return _write_report_deterministic(state)

    try:
        return _write_report_with_llm(state, llm_client=llm_client)
    except ReporterFallbackError:
        return _write_report_deterministic(state)


def _write_report_deterministic(state: GraphState) -> GraphState:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    reference_numbers = _build_reference_numbers(verified_evidence)
    lines = [
        "# InsightGraph Research Report",
        "",
        f"**Research Request:** {state.user_request}",
        "",
        "## Key Findings",
        "",
    ]
    for finding in state.findings:
        citations = " ".join(
            f"[{reference_numbers[eid]}]"
            for eid in finding.evidence_ids
            if eid in reference_numbers
        )
        if not citations:
            continue
        lines.extend([f"### {finding.title}", "", f"{finding.summary} {citations}".strip(), ""])

    lines.extend(_build_competitive_matrix_section(state.competitive_matrix, reference_numbers))
    lines.extend(_build_critic_assessment_section(state))
    lines.extend(_build_references_section(verified_evidence, reference_numbers))

    state.report_markdown = "\n".join(lines) + "\n"
    return state


def _write_report_with_llm(
    state: GraphState,
    llm_client: ChatCompletionClient | None = None,
) -> GraphState:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    reference_numbers = _build_reference_numbers(verified_evidence)
    if not reference_numbers:
        raise ReporterFallbackError("Verified references are required")

    config = resolve_llm_config()
    if llm_client is None:
        if not config.api_key:
            raise ReporterFallbackError("LLM api_key is required")
        llm_client = get_llm_client(config)

    wire_api = get_llm_wire_api(llm_client)
    messages = _build_reporter_messages(state, verified_evidence, reference_numbers)
    started = time.perf_counter()
    try:
        result = complete_json_with_observability(llm_client, messages)
    except (ValueError, TypeError) as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        state.llm_call_log.append(
            build_llm_call_record(
                stage="reporter",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=duration_ms,
                wire_api=wire_api,
                error=exc,
                secrets=[config.api_key],
            )
        )
        raise
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        state.llm_call_log.append(
            build_llm_call_record(
                stage="reporter",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=duration_ms,
                wire_api=wire_api,
                error=exc,
                secrets=[config.api_key],
            )
        )
        raise ReporterFallbackError("LLM reporter failed.") from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    try:
        body = _parse_llm_report_body(result.content)
        body = _strip_references_section(body)
        body = _normalize_smart_punctuation(body)
        _validate_llm_report_body(body, set(reference_numbers.values()))
    except ReporterFallbackError as exc:
        state.llm_call_log.append(
            build_llm_call_record(
                stage="reporter",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=duration_ms,
                wire_api=wire_api,
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
            stage="reporter",
            provider="llm",
            model=config.model,
            success=True,
            duration_ms=duration_ms,
            wire_api=wire_api,
            secrets=[config.api_key],
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
        )
    )

    matrix_lines = _build_competitive_matrix_section(
        state.competitive_matrix,
        reference_numbers,
    )
    body = _insert_competitive_matrix_section(body, matrix_lines)
    lines = [body.rstrip(), ""]
    if state.critique is not None and "## Critic Assessment" not in body:
        lines.extend(_build_critic_assessment_section(state))
    lines.extend(_build_references_section(verified_evidence, reference_numbers))

    state.report_markdown = "\n".join(lines).rstrip() + "\n"
    return state


def _build_reporter_messages(
    state: GraphState,
    verified_evidence: list[Evidence],
    reference_numbers: dict[str, int],
) -> list[ChatMessage]:
    finding_lines = []
    for finding in state.findings:
        citations = [
            f"[{reference_numbers[evidence_id]}]"
            for evidence_id in finding.evidence_ids
            if evidence_id in reference_numbers
        ]
        if not citations:
            continue
        finding_lines.append(
            "\n".join(
                [
                    f"- title: {finding.title}",
                    f"  summary: {finding.summary}",
                    f"  allowed_citations: {' '.join(citations)}",
                ]
            )
        )

    evidence_lines = []
    for item in verified_evidence:
        evidence_lines.append(
            "\n".join(
                [
                    f"- reference: [{reference_numbers[item.id]}]",
                    f"  id: {item.id}",
                    f"  title: {item.title}",
                    f"  url: {item.source_url}",
                    f"  source_type: {item.source_type}",
                    f"  snippet: {item.snippet}",
                ]
            )
        )

    critique_reason = (
        state.critique.reason if state.critique is not None else "No critique provided."
    )
    prompt = "\n\n".join(
        [
            f"User request: {state.user_request}",
            "Accepted findings with allowed citations:",
            "\n".join(finding_lines),
            "Verified evidence references:",
            "\n".join(evidence_lines),
            f"Critique reason: {critique_reason}",
            (
                "Return strict JSON only with this shape: "
                '{"markdown": "# InsightGraph Research Report\\n..."}. '
                "The markdown must include # InsightGraph Research Report and ## Key Findings. "
                "Use ASCII-only punctuation and quotes. "
                "Use only the allowed bracket citations, cite at least one source, and do not "
                "include References or Sources sections because references will be appended "
                "deterministically."
            ),
        ]
    )

    return [
        ChatMessage(
            role="system",
            content=(
                "You are a research reporter writing concise Markdown from verified evidence. "
                "Return JSON only."
            ),
        ),
        ChatMessage(role="user", content=prompt),
    ]


def _parse_llm_report_body(content: object) -> str:
    if not content:
        raise ReporterFallbackError("LLM response content is required")

    if isinstance(content, str):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ReporterFallbackError("LLM response must be valid JSON") from exc
    else:
        data = content

    if not isinstance(data, dict):
        raise ReporterFallbackError("LLM response must be a JSON object")

    markdown = data.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise ReporterFallbackError("LLM report markdown is required")
    return markdown.strip()


def _strip_references_section(markdown: str) -> str:
    return REFERENCE_HEADING_PATTERN.sub("", markdown).strip()


def _normalize_smart_punctuation(markdown: str) -> str:
    return markdown.translate(SMART_PUNCTUATION_TRANSLATION)


def _validate_llm_report_body(markdown: str, allowed_references: set[int]) -> None:
    if not markdown.startswith("# InsightGraph Research Report"):
        raise ReporterFallbackError("LLM report title is required")
    if "## Key Findings" not in markdown:
        raise ReporterFallbackError("LLM report Key Findings section is required")
    if RESIDUAL_REFERENCE_HEADING_PATTERN.search(markdown):
        raise ReporterFallbackError("LLM report must not include references or sources sections")

    key_findings = _key_findings_section(markdown)
    key_finding_citations = [int(match) for match in CITATION_PATTERN.findall(key_findings)]
    if not key_finding_citations:
        raise ReporterFallbackError("LLM Key Findings section must include at least one citation")

    citations = [int(match) for match in CITATION_PATTERN.findall(markdown)]
    if not citations:
        raise ReporterFallbackError("LLM report must include at least one citation")
    if not set(citations).issubset(allowed_references):
        raise ReporterFallbackError("LLM report cites unknown references")


def _key_findings_section(markdown: str) -> str:
    match = KEY_FINDINGS_HEADING_PATTERN.search(markdown)
    if match is None:
        raise ReporterFallbackError("LLM report Key Findings section is required")

    section_start = match.end()
    next_section = NEXT_SECTION_HEADING_PATTERN.search(markdown, section_start)
    section_end = next_section.start() if next_section is not None else len(markdown)
    return markdown[section_start:section_end]


def _build_reference_numbers(verified_evidence: list[Evidence]) -> dict[str, int]:
    return {item.id: index for index, item in enumerate(verified_evidence, start=1)}


def _build_competitive_matrix_section(
    matrix: list[CompetitiveMatrixRow],
    reference_numbers: dict[str, int],
) -> list[str]:
    rows = []
    for row in matrix:
        citations = [
            f"[{reference_numbers[evidence_id]}]"
            for evidence_id in row.evidence_ids
            if evidence_id in reference_numbers
        ]
        if not citations:
            continue
        strengths = "; ".join(row.strengths) if row.strengths else "Verified evidence available"
        rows.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(row.product),
                    _markdown_table_cell(row.positioning),
                    _markdown_table_cell(strengths),
                    ", ".join(citations),
                ]
            )
            + " |"
        )

    if not rows:
        return []
    return [
        "## Competitive Matrix",
        "",
        "| Product | Positioning | Strengths | Evidence |",
        "| --- | --- | --- | --- |",
        *rows,
        "",
    ]


def _has_competitive_matrix_section(body: str) -> bool:
    return COMPETITIVE_MATRIX_HEADING_PATTERN.search(body) is not None


def _insert_competitive_matrix_section(body: str, matrix_lines: list[str]) -> str:
    if not matrix_lines or _has_competitive_matrix_section(body):
        return body

    matrix_section = "\n".join(matrix_lines).rstrip()
    key_findings = KEY_FINDINGS_HEADING_PATTERN.search(body)
    if key_findings is None:
        return f"{body.rstrip()}\n\n{matrix_section}"

    next_section = NEXT_SECTION_HEADING_PATTERN.search(body, key_findings.end())
    if next_section is None:
        return f"{body.rstrip()}\n\n{matrix_section}"

    before = body[: next_section.start()].rstrip()
    after = body[next_section.start() :].lstrip()
    return f"{before}\n\n{matrix_section}\n\n{after}"


def _markdown_table_cell(value: str) -> str:
    return " ".join(value.replace("|", r"\|").splitlines())


def _build_critic_assessment_section(state: GraphState) -> list[str]:
    if state.critique is None:
        return []
    return ["## Critic Assessment", "", state.critique.reason, ""]


def _build_references_section(
    verified_evidence: list[Evidence], reference_numbers: dict[str, int]
) -> list[str]:
    lines = ["## References", ""]
    for item in verified_evidence:
        number = reference_numbers[item.id]
        lines.append(f"[{number}] {item.title}. {item.source_url}")
    return lines
