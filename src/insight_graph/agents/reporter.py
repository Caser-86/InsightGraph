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
from insight_graph.report_quality.report_review import (
    append_report_quality_diagnostics,
    strip_report_quality_diagnostics,
)
from insight_graph.report_quality.url_validation import validate_evidence_url
from insight_graph.state import CompetitiveMatrixRow, Evidence, Finding, GraphState, LLMCallRecord

CITATION_PATTERN = re.compile(r"\[(\d+)]")
REFERENCE_HEADING_PATTERN = re.compile(
    r"^ {0,3}#+\s*(references|sources)\b.*\Z", re.IGNORECASE | re.MULTILINE | re.DOTALL
)
RESIDUAL_REFERENCE_HEADING_PATTERN = re.compile(
    r"^ {0,3}#+\s*(references|sources)\b", re.IGNORECASE | re.MULTILINE
)
KEY_FINDINGS_HEADING_PATTERN = re.compile(r"(?im)^##\s+(?:核心发现|Key Findings)\s*$")
COMPETITIVE_MATRIX_HEADING_PATTERN = re.compile(
    r"(?im)^ {0,3}#{1,6}\s+(?:竞争矩阵|Competitive Matrix)\s*#*\s*$"
)
NEXT_SECTION_HEADING_PATTERN = re.compile(r"(?m)^ {0,3}#{1,6}\s+")
NEXT_MAJOR_SECTION_HEADING_PATTERN = re.compile(r"(?m)^ {0,3}#{1,2}\s+")
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
REPORTER_VALIDATE_URLS_ENV = "INSIGHT_GRAPH_REPORTER_VALIDATE_URLS"
REPORT_REVIEW_PROVIDER_ENV = "INSIGHT_GRAPH_REPORT_REVIEW_PROVIDER"
REQUIRED_REPORT_SECTIONS = (
    "摘要",
    "背景",
    "核心发现",
    "证据分析",
    "竞争格局",
    "趋势判断",
    "风险",
    "结论",
)
REPORT_TITLE = "# InsightGraph 深度研究报告"
LEGACY_REPORT_TITLE = "# InsightGraph Research Report"
KEY_FINDINGS_HEADINGS = ("核心发现", "Key Findings")


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
        state = _write_report_deterministic(state)
        return _finalize_report_quality(state)
    if not can_start_llm_call(state):
        state.llm_call_log.append(_budget_exhausted_record("reporter"))
        state = _write_report_deterministic(state)
        return _finalize_report_quality(state)

    try:
        state = _write_report_with_llm(state, llm_client=llm_client)
    except ReporterFallbackError:
        state = _write_report_deterministic(state)
    return _finalize_report_quality(state)


def _finalize_report_quality(state: GraphState) -> GraphState:
    state = _maybe_review_report_with_llm(state)
    return append_report_quality_diagnostics(state)


def _write_report_deterministic(state: GraphState) -> GraphState:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    _maybe_validate_reference_urls(state, verified_evidence)
    reference_numbers = _build_reference_numbers(verified_evidence)
    lines = [
        REPORT_TITLE,
        "",
        f"**研究问题：** {state.user_request}",
        "",
    ]
    lines.extend(_build_deterministic_body(state, verified_evidence, reference_numbers))

    lines.extend(_build_competitive_matrix_section(state.competitive_matrix, reference_numbers))
    lines.extend(_build_critic_assessment_section(state))
    lines.extend(_build_citation_support_section(state, reference_numbers))
    lines.extend(
        _build_references_section(verified_evidence, reference_numbers, state.url_validation)
    )

    state.report_markdown = "\n".join(lines) + "\n"
    return state


def _budget_exhausted_record(stage: str) -> LLMCallRecord:
    return LLMCallRecord(
        stage=stage,
        provider="llm",
        model="budget_exhausted",
        success=False,
        duration_ms=0,
        error="budget_exhausted",
    )


def _build_deterministic_body(
    state: GraphState,
    verified_evidence: list[Evidence],
    reference_numbers: dict[str, int],
) -> list[str]:
    supported_claims = _supported_claim_titles(state.citation_support)
    if not state.section_research_plan:
        return _build_standard_report_body(state, reference_numbers, supported_claims)
    if state.grounded_claims:
        return _build_grounded_claims_body(state, reference_numbers, supported_claims)
    if state.section_research_plan:
        return _complete_required_report_sections(
            _build_planned_section_body(
                state,
                verified_evidence,
                reference_numbers,
                supported_claims,
            )
        )
    return _build_key_findings_body(state, reference_numbers, supported_claims)


def _build_standard_report_body(
    state: GraphState,
    reference_numbers: dict[str, int],
    supported_claims: set[str] | None = None,
) -> list[str]:
    approved_lines = _approved_claim_lines(state, reference_numbers, supported_claims)
    summary = approved_lines[:2] or ["本节证据仍不足，需要继续补充来源。"]
    analysis = approved_lines or ["本节证据仍不足，需要继续补充来源。"]
    risks = _risk_lines(state.grounded_claims, supported_claims)
    if not risks:
        risks = ["本节证据仍不足，需要继续补充来源。"]
    return [
        "## 摘要",
        "",
        *summary,
        "",
        "## 背景",
        "",
        "本报告仅基于本次任务收集并验证过的证据展开。",
        "",
        "## 核心发现",
        "",
        *analysis,
        "",
        "## 证据分析",
        "",
        *analysis,
        "",
        "## 竞争格局",
        "",
        "竞争判断以已验证证据和竞争矩阵为依据。",
        "",
        "## 趋势判断",
        "",
        "现有证据显示该主题仍需要持续跟踪最新公开资料和产品动态。",
        "",
        "## 风险",
        "",
        *risks,
        "",
        "## 结论",
        "",
        "正式发布前应继续核验未充分支持或仅部分支持的判断。",
        "",
    ]


def _approved_claim_lines(
    state: GraphState,
    reference_numbers: dict[str, int],
    supported_claims: set[str] | None,
) -> list[str]:
    if state.grounded_claims:
        return _approved_grounded_claim_lines(state, reference_numbers, supported_claims)
    lines = []
    for finding in state.findings:
        if supported_claims is not None and finding.title not in supported_claims:
            continue
        citations = _finding_citations(finding.evidence_ids, reference_numbers)
        if citations:
            lines.append(f"- {finding.title}: {finding.summary} {citations}".strip())
    return lines


def _approved_grounded_claim_lines(
    state: GraphState,
    reference_numbers: dict[str, int],
    supported_claims: set[str] | None,
) -> list[str]:
    lines = []
    for claim in state.grounded_claims:
        claim_text = str(claim.get("claim", "")).strip()
        if not claim_text:
            continue
        if supported_claims is not None and claim_text not in supported_claims:
            continue
        evidence_ids = claim.get("evidence_ids", [])
        if not isinstance(evidence_ids, list):
            continue
        citations = _finding_citations(
            [item for item in evidence_ids if isinstance(item, str)],
            reference_numbers,
        )
        if citations:
            lines.append(f"- {claim_text} {citations}".strip())
    return lines


def _risk_lines(
    grounded_claims: list[dict[str, object]],
    supported_claims: set[str] | None,
) -> list[str]:
    lines = []
    for claim in grounded_claims:
        claim_text = str(claim.get("claim", "")).strip()
        risk = str(claim.get("risk", "")).strip()
        if not risk:
            continue
        if supported_claims is not None and claim_text not in supported_claims:
            continue
        lines.append(f"- {risk}")
    return lines


def _supported_claim_titles(citation_support: list[dict[str, object]]) -> set[str] | None:
    if not citation_support:
        return None
    return {
        str(item.get("claim", ""))
        for item in citation_support
        if item.get("support_status") == "supported"
    }


def _build_key_findings_body(
    state: GraphState,
    reference_numbers: dict[str, int],
    supported_claims: set[str] | None = None,
) -> list[str]:
    lines = ["## 核心发现", ""]
    for finding in state.findings:
        if supported_claims is not None and finding.title not in supported_claims:
            continue
        citations = _finding_citations(finding.evidence_ids, reference_numbers)
        if not citations:
            continue
        lines.extend([f"### {finding.title}", "", f"{finding.summary} {citations}".strip(), ""])
    return lines


def _build_grounded_claims_body(
    state: GraphState,
    reference_numbers: dict[str, int],
    supported_claims: set[str] | None = None,
) -> list[str]:
    lines = ["## 核心发现", ""]
    for claim in state.grounded_claims:
        claim_text = str(claim.get("claim", "")).strip()
        if not claim_text:
            continue
        if supported_claims is not None and claim_text not in supported_claims:
            continue
        evidence_ids = claim.get("evidence_ids", [])
        if not isinstance(evidence_ids, list):
            continue
        citations = _finding_citations(
            [evidence_id for evidence_id in evidence_ids if isinstance(evidence_id, str)],
            reference_numbers,
        )
        if not citations:
            continue
        lines.extend([f"- {claim_text} {citations}".strip()])
    if len(lines) == 2:
        lines.extend(["本节暂无可引用的支持性发现。"])
    lines.append("")
    return lines


def _build_planned_section_body(
    state: GraphState,
    verified_evidence: list[Evidence],
    reference_numbers: dict[str, int],
    supported_claims: set[str] | None = None,
) -> list[str]:
    evidence_sections = {item.id: item.section_id for item in verified_evidence}
    assigned_findings = _assign_findings_to_sections(
        state.findings,
        evidence_sections,
        reference_numbers,
    )
    lines: list[str] = []
    for section in state.section_research_plan:
        section_id = str(section.get("section_id", "")).strip()
        title = str(section.get("title", "")).strip()
        if not title or title.lower() in {"references", "sources", "参考资料", "来源"}:
            continue
        lines.extend([f"## {_localized_section_title(title)}", ""])
        section_findings = assigned_findings.get(section_id, [])
        if not section_findings:
            lines.extend(["本节暂无已验证发现。", ""])
            continue
        for finding in section_findings:
            if supported_claims is not None and finding.title not in supported_claims:
                continue
            citations = _finding_citations(finding.evidence_ids, reference_numbers)
            lines.extend([f"### {finding.title}", "", f"{finding.summary} {citations}".strip(), ""])
    return lines


def _localized_section_title(title: str) -> str:
    return {
        "Executive Summary": "摘要",
        "Background": "背景",
        "Key Findings": "核心发现",
        "Analysis": "证据分析",
        "Competitive Landscape": "竞争格局",
        "Risks": "风险",
        "Outlook": "结论",
    }.get(title, title)


def _complete_required_report_sections(
    lines: list[str],
    *,
    require_generic_analysis: bool = False,
) -> list[str]:
    body = "\n".join(lines)
    existing_titles = _report_section_titles(body)
    title_lines, lines = _pop_report_title(lines)
    executive_summary, remaining_lines = _pop_section(lines, "摘要")
    key_findings, remaining_lines = _pop_section(remaining_lines, "核心发现")
    output: list[str] = [*title_lines]

    def append_missing(title: str) -> None:
        if title in existing_titles:
            return
        output.extend([f"## {title}", "", "本节证据仍不足，需要继续补充来源。", ""])

    if executive_summary:
        output.extend(executive_summary)
    else:
        append_missing("摘要")
    append_missing("背景")
    if key_findings:
        output.extend(key_findings)
    else:
        append_missing("核心发现")
    if require_generic_analysis:
        append_missing("证据分析")
    competitive_landscape, remaining_lines = _pop_section(
        remaining_lines,
        "竞争格局",
    )
    trend, remaining_lines = _pop_section(remaining_lines, "趋势判断")
    risks, remaining_lines = _pop_section(remaining_lines, "风险")
    outlook, remaining_lines = _pop_section(remaining_lines, "结论")
    output.extend(remaining_lines)
    for title, existing_section in (
        ("竞争格局", competitive_landscape),
        ("趋势判断", trend),
        ("风险", risks),
        ("结论", outlook),
    ):
        if existing_section:
            output.extend(existing_section)
            continue
        append_missing(title)
    return output


def _pop_report_title(lines: list[str]) -> tuple[list[str], list[str]]:
    if not lines or not lines[0].startswith("# ") or lines[0].startswith("## "):
        return [], lines

    end = 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return lines[:end], lines[end:]


def _pop_section(lines: list[str], title: str) -> tuple[list[str], list[str]]:
    heading = f"## {title}"
    start = next((index for index, line in enumerate(lines) if line.strip() == heading), None)
    if start is None:
        return [], lines
    end = next(
        (
            index
            for index, line in enumerate(lines[start + 1 :], start=start + 1)
            if line.startswith("## ") and not line.startswith("### ")
        ),
        len(lines),
    )
    return lines[start:end], [*lines[:start], *lines[end:]]


def _report_section_titles(markdown: str) -> set[str]:
    titles: set[str] = set()
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("## ") or stripped.startswith("### "):
            continue
        titles.add(stripped.removeprefix("## ").strip(" #"))
    return titles


def _assign_findings_to_sections(
    findings: list[Finding],
    evidence_sections: dict[str, str | None],
    reference_numbers: dict[str, int],
) -> dict[str, list[Finding]]:
    assigned: dict[str, list[Finding]] = {}
    for finding in findings:
        if not _finding_citations(finding.evidence_ids, reference_numbers):
            continue
        section_id = _first_finding_section_id(finding.evidence_ids, evidence_sections)
        if section_id is None:
            continue
        assigned.setdefault(section_id, []).append(finding)
    return assigned


def _first_finding_section_id(
    evidence_ids: list[str],
    evidence_sections: dict[str, str | None],
) -> str | None:
    for evidence_id in evidence_ids:
        section_id = evidence_sections.get(evidence_id)
        if section_id:
            return section_id
    return None


def _finding_citations(
    evidence_ids: list[str],
    reference_numbers: dict[str, int],
) -> str:
    return " ".join(
        f"[{reference_numbers[eid]}]" for eid in evidence_ids if eid in reference_numbers
    )


def _write_report_with_llm(
    state: GraphState,
    llm_client: ChatCompletionClient | None = None,
) -> GraphState:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    _maybe_validate_reference_urls(state, verified_evidence)
    reference_numbers = _build_reference_numbers(verified_evidence)
    if not reference_numbers:
        raise ReporterFallbackError("Verified references are required")

    config = resolve_llm_config()
    messages = _build_reporter_messages(state, verified_evidence, reference_numbers)
    if llm_client is None:
        if not config.api_key:
            raise ReporterFallbackError("LLM api_key is required")
        llm_client = get_llm_client(config, purpose="reporter", messages=messages)

    wire_api = get_llm_wire_api(llm_client)
    started = time.perf_counter()
    try:
        result = complete_json_with_observability(llm_client, messages)
    except (ValueError, TypeError) as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        state.llm_call_log.append(
            build_llm_call_record(
                stage="reporter",
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
            stage="reporter",
            llm_client=llm_client,
            messages=messages,
            output_text="",
            duration_ms=duration_ms,
            success=False,
            error=exc,
        )
        raise
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        state.llm_call_log.append(
            build_llm_call_record(
                stage="reporter",
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
            stage="reporter",
            llm_client=llm_client,
            messages=messages,
            output_text="",
            duration_ms=duration_ms,
            success=False,
            error=exc,
        )
        raise ReporterFallbackError("LLM reporter failed.") from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    try:
        body = _parse_llm_report_body(result.content)
        body = _strip_references_section(body)
        body = _normalize_smart_punctuation(body)
        body = _normalize_report_language_headings(body)
        matrix_lines = _build_competitive_matrix_section(
            state.competitive_matrix,
            reference_numbers,
        )
        body = _prepare_competitive_matrix_section(
            body,
            matrix_lines,
            set(reference_numbers.values()),
        )
        body = _complete_required_report_body(body)
        _validate_llm_report_body(body, set(reference_numbers.values()))
    except ReporterFallbackError as exc:
        state.llm_call_log.append(
            build_llm_call_record(
                stage="reporter",
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
        raise

    state.llm_call_log.append(
        build_llm_call_record(
            stage="reporter",
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
        stage="reporter",
        llm_client=llm_client,
        messages=messages,
        output_text=result.content or "",
        duration_ms=duration_ms,
        success=True,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
    )

    lines = [body.rstrip(), ""]
    if state.critique is not None and not (
        "## 质量评审" in body or "## Critic Assessment" in body
    ):
        lines.extend(_build_critic_assessment_section(state))
    lines.extend(_build_citation_support_section(state, reference_numbers))
    lines.extend(
        _build_references_section(verified_evidence, reference_numbers, state.url_validation)
    )

    state.report_markdown = "\n".join(lines).rstrip() + "\n"
    return state


def _report_review_provider() -> str:
    provider = os.getenv(REPORT_REVIEW_PROVIDER_ENV, "deterministic").strip().lower()
    if provider in {"", "deterministic", "none"}:
        return "deterministic"
    if provider == "llm":
        return "llm"
    raise ValueError(f"Unknown report review provider: {provider}")


def _maybe_review_report_with_llm(state: GraphState) -> GraphState:
    if _report_review_provider() != "llm":
        return state
    if not can_start_llm_call(state):
        state.llm_call_log.append(_budget_exhausted_record("report_review"))
        return state

    verified_evidence = [item for item in state.evidence_pool if item.verified]
    reference_numbers = _build_reference_numbers(verified_evidence)
    if not reference_numbers or not state.report_markdown:
        return state

    config = resolve_llm_config()
    if not config.api_key:
        state.llm_call_log.append(
            LLMCallRecord(
                stage="report_review",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=0,
                error="api_key_required",
            )
        )
        return state

    messages = _build_report_review_messages(state, verified_evidence, reference_numbers)
    llm_client = get_llm_client(config, purpose="report_review", messages=messages)
    wire_api = get_llm_wire_api(llm_client)
    started = time.perf_counter()
    try:
        result = complete_json_with_observability(llm_client, messages)
        reviewed_body = _parse_llm_report_body(result.content)
        reviewed_body = _strip_references_section(reviewed_body)
        reviewed_body = strip_report_quality_diagnostics(reviewed_body)
        reviewed_body = _normalize_smart_punctuation(reviewed_body)
        reviewed_body = _normalize_report_language_headings(reviewed_body)
        reviewed_body = _complete_required_report_body(reviewed_body)
        _validate_llm_report_body(reviewed_body, set(reference_numbers.values()))
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        state.llm_call_log.append(
            build_llm_call_record(
                stage="report_review",
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
        return state

    duration_ms = int((time.perf_counter() - started) * 1000)
    state.llm_call_log.append(
        build_llm_call_record(
            stage="report_review",
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
    state.report_markdown = (
        "\n".join(
            [
                reviewed_body.rstrip(),
                "",
                *_build_references_section(
                    verified_evidence,
                    reference_numbers,
                    state.url_validation,
                ),
            ]
        ).rstrip()
        + "\n"
    )
    return state


def _build_report_review_messages(
    state: GraphState,
    verified_evidence: list[Evidence],
    reference_numbers: dict[str, int],
) -> list[ChatMessage]:
    evidence_lines = []
    for item in verified_evidence:
        evidence_lines.append(
            "\n".join(
                [
                    f"- reference: [{reference_numbers[item.id]}]",
                    f"  title: {item.title}",
                    f"  url: {item.source_url}",
                    f"  source_type: {item.source_type}",
                    f"  snippet: {item.snippet}",
                ]
            )
        )
    report_body = _strip_references_section(
        strip_report_quality_diagnostics(state.report_markdown or "")
    )
    prompt = "\n\n".join(
        [
            f"User request: {state.user_request}",
            "Current report markdown without deterministic references:",
            report_body,
            "Verified evidence and allowed citations:",
            "\n".join(evidence_lines),
            (
                "请对这份中文研究报告做一次审稿式润色和适度扩写："
                "让行文更顺、段落更完整、证据解释更充分、风险边界更清楚。"
                "只能使用上面 verified evidence 中已有事实；不要新增来源、数字或未经证实的判断。"
                "只能使用允许的 [n] 引用；不要生成 References 或 Sources。"
                "Return strict JSON only: {\"markdown\":\"# InsightGraph 深度研究报告\\n...\"}."
            ),
        ]
    )
    return [
        ChatMessage(
            role="system",
            content=(
                "You are a senior Chinese editor for evidence-grounded research reports. "
                "Return JSON only."
            ),
        ),
        ChatMessage(role="user", content=prompt),
    ]


def _url_validation_enabled() -> bool:
    return os.getenv(REPORTER_VALIDATE_URLS_ENV, "").lower() in {"1", "true", "yes"}


def _maybe_validate_reference_urls(state: GraphState, evidence: list[Evidence]) -> None:
    if not _url_validation_enabled():
        return
    state.url_validation = [validate_evidence_url(item) for item in evidence]


def _build_reporter_messages(
    state: GraphState,
    verified_evidence: list[Evidence],
    reference_numbers: dict[str, int],
) -> list[ChatMessage]:
    supported_claims = _supported_claim_titles(state.citation_support)
    finding_lines = []
    for finding in state.findings:
        if supported_claims is not None and finding.title not in supported_claims:
            continue
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
            "Verified evidence snippets:",
            "\n".join(evidence_lines),
            f"Critique reason: {critique_reason}",
            "Evidence snippets are the only allowed factual basis.",
            (
                "默认输出中文深度研究报告，除非用户明确要求其他语言。"
                "报告必须文理通顺、段落完整，至少覆盖摘要、背景、证据分析、趋势判断、风险、结论，"
                "并包含核心发现、"
                "证据分析、竞争格局或相关对比、趋势判断、风险、结论。"
                "每个核心判断都要解释证据含义和业务/研究影响，避免只罗列短句。"
                "必须使用 Markdown 标题：# InsightGraph 深度研究报告、## 摘要、"
                "## 背景、## 核心发现、## 证据分析、## 竞争格局、## 风险、## 结论。"
                "每段事实性判断必须使用允许的引用。"
                "Return strict JSON only with this shape: "
                '{"markdown": "# InsightGraph 深度研究报告\\n..."}. '
                "The markdown must include # InsightGraph 深度研究报告 and ## 核心发现. "
                "Use ASCII-only punctuation and quotes. "
                "Use only facts and numbers present in the verified evidence snippets. "
                "Use only the allowed bracket citations, cite at least one source, and do not "
                "include References or Sources sections because references will be appended "
                "deterministically. Do not invent facts, numbers, sources, or citations."
            ),
        ]
    )

    return [
        ChatMessage(
            role="system",
            content=(
                "You are a senior Chinese research reporter writing fluent, substantial "
                "Markdown from verified evidence. Return JSON only."
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


def _normalize_report_language_headings(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].strip() == LEGACY_REPORT_TITLE:
        lines[0] = REPORT_TITLE
    heading_map = {
        "## Executive Summary": "## 摘要",
        "## Background": "## 背景",
        "## Key Findings": "## 核心发现",
        "## Analysis": "## 证据分析",
        "## Competitive Landscape": "## 竞争格局",
        "## Competitive Matrix": "## 竞争矩阵",
        "## Risks": "## 风险",
        "## Outlook": "## 结论",
        "## Citation Support": "## 引用支持",
        "## Critic Assessment": "## 质量评审",
    }
    normalized = []
    for line in lines:
        stripped = line.strip()
        if COMPETITIVE_MATRIX_HEADING_PATTERN.match(stripped):
            normalized.append("## 竞争矩阵")
            continue
        if re.match(r"(?i)^#{1,6}\s+key findings\s*#*\s*$", stripped):
            normalized.append("## 核心发现")
            continue
        if re.match(r"(?i)^#{1,6}\s+critic assessment\s*#*\s*$", stripped):
            normalized.append("## 质量评审")
            continue
        normalized.append(heading_map.get(stripped, line))
    return "\n".join(normalized)


def _validate_llm_report_body(markdown: str, allowed_references: set[int]) -> None:
    if not (
        markdown.startswith(REPORT_TITLE)
        or markdown.startswith(LEGACY_REPORT_TITLE)
    ):
        raise ReporterFallbackError("LLM report title is required")
    if not any(f"## {heading}" in markdown for heading in KEY_FINDINGS_HEADINGS):
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


def _complete_required_report_body(markdown: str) -> str:
    lines = _complete_required_report_sections(
        markdown.splitlines(),
        require_generic_analysis=True,
    )
    return "\n".join(lines).strip()


def _key_findings_section(markdown: str) -> str:
    match = KEY_FINDINGS_HEADING_PATTERN.search(markdown)
    if match is None:
        raise ReporterFallbackError("LLM report Key Findings section is required")

    section_start = match.end()
    next_section = NEXT_MAJOR_SECTION_HEADING_PATTERN.search(markdown, section_start)
    section_end = next_section.start() if next_section is not None else len(markdown)
    return markdown[section_start:section_end]


def _build_reference_numbers(verified_evidence: list[Evidence]) -> dict[str, int]:
    return {item.id: index for index, item in enumerate(verified_evidence, start=1)}


def _build_competitive_matrix_section(
    matrix: list[CompetitiveMatrixRow],
    reference_numbers: dict[str, int],
) -> list[str]:
    rows = []
    has_v2_fields = any(_matrix_row_has_v2_fields(row) for row in matrix)
    for row in matrix:
        citations = [
            f"[{reference_numbers[evidence_id]}]"
            for evidence_id in row.evidence_ids
            if evidence_id in reference_numbers
        ]
        if not citations:
            continue
        strengths = "; ".join(row.strengths) if row.strengths else "Verified evidence available"
        cells = [
            _markdown_table_cell(row.product),
            _markdown_table_cell(row.positioning),
            _markdown_table_cell(strengths),
        ]
        if has_v2_fields:
            cells.extend(
                [
                    _markdown_table_cell(row.pricing or ""),
                    _markdown_table_cell(_matrix_list_cell(row.features)),
                    _markdown_table_cell(_matrix_list_cell(row.integrations)),
                    _markdown_table_cell(_matrix_list_cell(row.target_users)),
                    _markdown_table_cell(_matrix_list_cell(row.risks)),
                ]
            )
        cells.append(", ".join(citations))
        rows.append("| " + " | ".join(cells) + " |")

    if not rows:
        return []
    header = "| Product | Positioning | Strengths | Evidence |"
    separator = "| --- | --- | --- | --- |"
    if has_v2_fields:
        header = (
            "| Product | Positioning | Strengths | Pricing | Features | Integrations | "
            "Target Users | Risks | Evidence |"
        )
        separator = "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    return ["## 竞争矩阵", "", header, separator, *rows, ""]


def _matrix_row_has_v2_fields(row: CompetitiveMatrixRow) -> bool:
    return bool(row.pricing or row.features or row.integrations or row.target_users or row.risks)


def _matrix_list_cell(values: list[str]) -> str:
    return "; ".join(values)


def _has_competitive_matrix_section(body: str) -> bool:
    return COMPETITIVE_MATRIX_HEADING_PATTERN.search(body) is not None


def _prepare_competitive_matrix_section(
    body: str,
    matrix_lines: list[str],
    allowed_references: set[int],
) -> str:
    matrix_range = _competitive_matrix_section_range(body)
    if matrix_range is None:
        return _insert_competitive_matrix_section(body, matrix_lines)

    start, end = matrix_range
    matrix_section = body[start:end]
    if _matrix_section_has_only_allowed_data_row_citations(
        matrix_section,
        allowed_references,
    ):
        return body

    without_matrix = f"{body[:start].rstrip()}\n\n{body[end:].lstrip()}".strip()
    return _insert_competitive_matrix_section(without_matrix, matrix_lines)


def _competitive_matrix_section_range(body: str) -> tuple[int, int] | None:
    match = COMPETITIVE_MATRIX_HEADING_PATTERN.search(body)
    if match is None:
        return None

    next_section = NEXT_SECTION_HEADING_PATTERN.search(body, match.end())
    section_end = next_section.start() if next_section is not None else len(body)
    return match.start(), section_end


def _matrix_section_has_only_allowed_data_row_citations(
    matrix_section: str,
    allowed_references: set[int],
) -> bool:
    has_data_row = False
    for line in matrix_section.splitlines():
        stripped = line.strip()
        if not _is_matrix_data_row(stripped):
            continue
        has_data_row = True
        citations = [int(match) for match in CITATION_PATTERN.findall(stripped)]
        if not any(citation in allowed_references for citation in citations):
            return False
    return has_data_row


def _is_matrix_data_row(line: str) -> bool:
    if not line.startswith("|"):
        return False

    cells = [cell.strip() for cell in line.strip("|").split("|")]
    normalized_cells = [cell.lower() for cell in cells]
    if normalized_cells == ["product", "positioning", "strengths", "evidence"]:
        return False

    return not all(set(cell) <= {"-", ":", " "} for cell in cells)


def _insert_competitive_matrix_section(body: str, matrix_lines: list[str]) -> str:
    if not matrix_lines or _has_competitive_matrix_section(body):
        return body

    matrix_section = "\n".join(matrix_lines).rstrip()
    key_findings = KEY_FINDINGS_HEADING_PATTERN.search(body)
    if key_findings is None:
        return f"{body.rstrip()}\n\n{matrix_section}"

    next_section = NEXT_MAJOR_SECTION_HEADING_PATTERN.search(body, key_findings.end())
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
    return ["## 质量评审", "", state.critique.reason, ""]


def _build_citation_support_section(
    state: GraphState,
    reference_numbers: dict[str, int],
) -> list[str]:
    if not state.citation_support:
        return [
            "## 引用支持",
            "",
            "本节证据仍不足，需要继续补充来源。",
            "",
        ]

    rows = []
    has_verified_support = False
    for item in state.citation_support:
        claim = str(item.get("claim", ""))
        status = str(item.get("support_status", "unknown"))
        reason = _citation_support_reason(item)
        evidence_ids = item.get("evidence_ids", [])
        verified_ids = [
            evidence_id
            for evidence_id in evidence_ids
            if isinstance(evidence_id, str) and evidence_id in reference_numbers
        ]
        has_verified_support = has_verified_support or bool(verified_ids)
        rows.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(claim),
                    _markdown_table_cell(status),
                    _markdown_table_cell(", ".join(verified_ids)),
                    _markdown_table_cell(reason),
                ]
            )
            + " |"
        )

    if not has_verified_support:
        return []

    return [
        "## 引用支持",
        "",
        "| Claim | Status | Evidence | Reason |",
        "| --- | --- | --- | --- |",
        *rows,
        "",
    ]


def _citation_support_reason(item: dict[str, object]) -> str:
    unsupported_reason = item.get("unsupported_reason")
    parts = [unsupported_reason if isinstance(unsupported_reason, str) else ""]
    support_score = item.get("support_score")
    if isinstance(support_score, int | float):
        parts.append(f"support_score={support_score}")
    matched_terms = item.get("matched_terms")
    if isinstance(matched_terms, list) and matched_terms:
        terms = [term for term in matched_terms if isinstance(term, str)]
        if terms:
            parts.append(f"matched_terms={', '.join(terms)}")
    return "; ".join(part for part in parts if part)


def _build_references_section(
    verified_evidence: list[Evidence],
    reference_numbers: dict[str, int],
    url_validation: list[dict[str, object]] | None = None,
) -> list[str]:
    lines = ["## References", ""]
    validation_by_id = {
        str(item.get("evidence_id")): item
        for item in url_validation or []
        if isinstance(item.get("evidence_id"), str)
    }
    for item in verified_evidence:
        number = reference_numbers[item.id]
        note = _reference_validation_note(validation_by_id.get(item.id))
        lines.append(f"[{number}] {item.title}. {item.source_url}{note}")
    return lines


def _reference_validation_note(validation: dict[str, object] | None) -> str:
    if validation is None:
        return ""
    if validation.get("valid") is True:
        return " (URL validated)"
    error = validation.get("error")
    if isinstance(error, str) and error:
        return f" (URL validation failed: {error})"
    return " (URL validation failed)"
