from __future__ import annotations

import re
from typing import Any

from insight_graph.report_quality.intensity import get_report_intensity_config
from insight_graph.report_quality.fact_mapping import build_fact_conclusion_mapping
from insight_graph.state import GraphState

SECTION_PATTERN = re.compile(r"(?m)^##\s+(.+?)\s*$")
WORD_PATTERN = re.compile(r"[\w]+", re.UNICODE)
CITATION_PATTERN = re.compile(r"\[(\d+)]")
REQUIRED_SECTIONS = (
    "摘要",
    "背景",
    "核心发现",
    "证据分析",
    "竞争格局",
    "趋势判断",
    "风险",
    "结论",
)
EMPTY_SECTION_MARKERS = (
    "暂无已验证",
    "证据仍不足",
    "暂无",
)


def build_report_quality_review(
    state: GraphState,
    report_markdown: str,
    *,
    intensity: str | None = None,
) -> dict[str, Any]:
    config = get_report_intensity_config(intensity)
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    verified_ids = {item.id for item in verified_evidence}
    headings = _section_headings(report_markdown)
    present_sections = [section for section in REQUIRED_SECTIONS if section in headings]
    missing_sections = [section for section in REQUIRED_SECTIONS if section not in headings]
    claim_count = len(state.findings) + len(state.competitive_matrix)
    supported_claims = _supported_claim_count(state, verified_ids)
    citation_count = len(CITATION_PATTERN.findall(report_markdown))
    source_types = {item.source_type for item in verified_evidence}
    source_domains = {item.source_domain for item in verified_evidence}
    word_count = len(WORD_PATTERN.findall(report_markdown))
    empty_sections = _empty_sections(report_markdown)
    risk_present = "## 风险" in report_markdown and "风险" in report_markdown
    fact_mapping = build_fact_conclusion_mapping(state)
    citation_summary = _citation_support_summary(state)

    metrics = {
        "section_coverage_score": _percentage(len(present_sections), len(REQUIRED_SECTIONS)),
        "citation_support_score": 100
        if claim_count == 0
        else _percentage(supported_claims, claim_count),
        "source_diversity_score": min(100, round(len(source_types) / 3 * 100)),
        "evidence_depth_score": min(
            100,
            _percentage(len(verified_evidence), config.min_verified_evidence),
        ),
        "report_depth_score": min(100, _percentage(word_count, config.target_words)),
        "risk_coverage_score": 100 if risk_present else 0,
        "verified_evidence_count": len(verified_evidence),
        "unique_source_type_count": len(source_types),
        "unique_source_domain_count": len(source_domains),
        "claim_count": claim_count,
        "supported_claim_count": supported_claims,
        "citation_count": citation_count,
        "word_count": word_count,
        "empty_sections": empty_sections,
        "missing_sections": missing_sections,
        "citation_support_total": citation_summary["total"],
        "citation_supported_count": citation_summary["supported_count"],
        "citation_partial_count": citation_summary["partial_count"],
        "citation_unsupported_count": citation_summary["unsupported_count"],
        "citation_supported_ratio": citation_summary["supported_ratio"],
        "conclusion_count": int(fact_mapping.get("conclusion_count", 0)),
        "mapped_conclusion_count": int(fact_mapping.get("mapped_conclusion_count", 0)),
        "weak_conclusion_count": int(fact_mapping.get("weak_conclusion_count", 0)),
        "fact_mapping_score": int(fact_mapping.get("mapping_score", 0)),
    }
    score = round(
        metrics["section_coverage_score"] * 0.20
        + metrics["citation_support_score"] * 0.25
        + metrics["source_diversity_score"] * 0.20
        + metrics["evidence_depth_score"] * 0.15
        + metrics["report_depth_score"] * 0.10
        + metrics["risk_coverage_score"] * 0.05
        + metrics["fact_mapping_score"] * 0.05
    )
    gaps, actions = _quality_gaps(metrics, config.name)
    strengths = _quality_strengths(metrics)
    return {
        "score": score,
        "status": "pass" if score >= 80 and not empty_sections else "needs_improvement",
        "intensity": config.name,
        "intensity_label": config.label,
        "strengths": strengths,
        "gaps": gaps,
        "recommended_actions": actions,
        "metrics": metrics,
    }


def format_report_quality_diagnostics(review: dict[str, Any]) -> list[str]:
    metrics = review.get("metrics", {})
    strengths = _string_list(review.get("strengths"))
    gaps = _string_list(review.get("gaps"))
    actions = _string_list(review.get("recommended_actions"))
    lines = [
        "## 报告质量诊断",
        "",
        f"- 综合评分：{review.get('score', 0)}/100",
        f"- 报告强度：{review.get('intensity_label', review.get('intensity', 'standard'))}",
        f"- 引用支撑率：{metrics.get('citation_support_score', 0)}%",
        (
            f"- 来源多样性：{metrics.get('unique_source_type_count', 0)} 类来源，"
            f"{metrics.get('unique_source_domain_count', 0)} 个域名"
        ),
        f"- 已验证证据：{metrics.get('verified_evidence_count', 0)} 条",
        f"- 报告长度：约 {metrics.get('word_count', 0)} 个词/字词单元",
    ]
    if strengths:
        lines.append(f"- 优势：{'；'.join(strengths)}")
    if gaps:
        lines.append(f"- 薄弱项：{'；'.join(gaps)}")
    if actions:
        lines.append(f"- 建议：{'；'.join(actions)}")
    lines.append("")
    return lines


def append_report_quality_diagnostics(state: GraphState) -> GraphState:
    markdown = state.report_markdown or ""
    body = strip_report_quality_diagnostics(markdown).rstrip()
    review = build_report_quality_review(state, body)
    state.report_quality_review = review
    state.report_markdown = "\n".join([body, "", *format_report_quality_diagnostics(review)])
    return state


def strip_report_quality_diagnostics(markdown: str) -> str:
    marker = "\n## 报告质量诊断"
    index = markdown.find(marker)
    if index == -1:
        return markdown
    return markdown[:index].rstrip() + "\n"


def _section_headings(report_markdown: str) -> list[str]:
    return [
        match.group(1).strip().rstrip("#").strip()
        for match in SECTION_PATTERN.finditer(report_markdown)
    ]


def _supported_claim_count(state: GraphState, verified_ids: set[str]) -> int:
    supported = 0
    for finding in state.findings:
        if finding.evidence_ids and all(
            evidence_id in verified_ids for evidence_id in finding.evidence_ids
        ):
            supported += 1
    for row in state.competitive_matrix:
        if row.evidence_ids and all(
            evidence_id in verified_ids for evidence_id in row.evidence_ids
        ):
            supported += 1
    return supported


def _empty_sections(report_markdown: str) -> list[str]:
    headings = list(SECTION_PATTERN.finditer(report_markdown))
    empty: list[str] = []
    for index, match in enumerate(headings):
        section_end = (
            headings[index + 1].start()
            if index + 1 < len(headings)
            else len(report_markdown)
        )
        section_text = report_markdown[match.end() : section_end]
        if any(marker in section_text for marker in EMPTY_SECTION_MARKERS):
            empty.append(match.group(1).strip())
    return empty


def _quality_gaps(metrics: dict[str, Any], intensity: str) -> tuple[list[str], list[str]]:
    gaps: list[str] = []
    actions: list[str] = []
    if metrics["verified_evidence_count"] < 3:
        gaps.append("已验证证据不足")
        actions.append("补充已验证证据，优先使用官方、文档、新闻或财报来源")
    if metrics["source_diversity_score"] < 67:
        gaps.append("来源类型不够多元")
        actions.append("扩大搜索范围，覆盖官方文档、新闻、GitHub/SEC/论文等来源")
    if metrics["citation_support_score"] < 80:
        gaps.append("部分结论引用支撑不足")
        actions.append("减少无引用判断，或补充能直接支撑结论的证据")
    if metrics["missing_sections"]:
        gaps.append("缺少必要章节")
        actions.append("补齐摘要、背景、核心发现、证据分析、竞争格局、趋势、风险和结论")
    if metrics["empty_sections"]:
        gaps.append("存在空泛或证据不足章节")
        actions.append("针对薄弱章节补搜并重写段落")
    if intensity in {"deep", "deep-plus"} and metrics["report_depth_score"] < 70:
        gaps.append("高强度报告篇幅仍偏短")
        actions.append("在保持引用约束的前提下扩写证据解释和业务影响")
    if metrics.get("fact_mapping_score", 0) < 80:
        gaps.append("结论到证据映射偏弱")
        actions.append("补充结论到证据的逐条映射，删除无法支撑的判断")
    if metrics.get("citation_supported_ratio", 100) < 80:
        gaps.append("引用采纳率偏低")
        actions.append("优先保留 supported 结论，并针对 unsupported 结论补证")
    return gaps, actions


def _quality_strengths(metrics: dict[str, Any]) -> list[str]:
    strengths: list[str] = []
    if metrics["verified_evidence_count"] >= 3:
        strengths.append("已具备基础已验证证据")
    if metrics["source_diversity_score"] >= 67:
        strengths.append("来源类型较多元")
    if metrics["citation_support_score"] >= 80:
        strengths.append("主要结论具备引用支撑")
    if metrics["section_coverage_score"] >= 80:
        strengths.append("报告章节较完整")
    return strengths


def _percentage(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 100
    return round(numerator / denominator * 100)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _citation_support_summary(state: GraphState) -> dict[str, int]:
    total = len(state.citation_support)
    supported = 0
    partial = 0
    unsupported = 0
    for item in state.citation_support:
        status = item.get("support_status")
        if status == "supported":
            supported += 1
        elif status == "partial":
            partial += 1
        else:
            unsupported += 1
    return {
        "total": total,
        "supported_count": supported,
        "partial_count": partial,
        "unsupported_count": unsupported,
        "supported_ratio": 100 if total == 0 else round(supported / total * 100),
    }
