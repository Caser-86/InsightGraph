import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from insight_graph.graph import run_research
from insight_graph.state import GraphState

OFFLINE_ENV_VARS = [
    "INSIGHT_GRAPH_ANALYST_PROVIDER",
    "INSIGHT_GRAPH_REPORTER_PROVIDER",
    "INSIGHT_GRAPH_LLM_API_KEY",
    "INSIGHT_GRAPH_LLM_BASE_URL",
    "INSIGHT_GRAPH_LLM_MODEL",
    "INSIGHT_GRAPH_LLM_WIRE_API",
    "INSIGHT_GRAPH_USE_WEB_SEARCH",
    "INSIGHT_GRAPH_USE_GITHUB_SEARCH",
    "INSIGHT_GRAPH_USE_NEWS_SEARCH",
    "INSIGHT_GRAPH_USE_DOCUMENT_READER",
    "INSIGHT_GRAPH_USE_READ_FILE",
    "INSIGHT_GRAPH_USE_LIST_DIRECTORY",
    "INSIGHT_GRAPH_USE_WRITE_FILE",
    "INSIGHT_GRAPH_SEARCH_PROVIDER",
    "INSIGHT_GRAPH_SEARCH_LIMIT",
    "INSIGHT_GRAPH_RELEVANCE_FILTER",
    "INSIGHT_GRAPH_RELEVANCE_JUDGE",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
]

REFERENCE_LINE_PATTERN = re.compile(r"(?m)^\[\d+]\s+")
SAFE_WORKFLOW_ERROR = "Research workflow failed."
PASSING_SCORE = 80
RULE_IDS = [
    "critique_passed",
    "has_report",
    "has_competitive_matrix_section",
    "references_meet_minimum",
    "findings_meet_minimum",
    "matrix_rows_meet_minimum",
    "findings_cite_evidence",
    "matrix_rows_cite_evidence",
]
REQUIRED_REPORT_SECTIONS = [
    "Key Findings",
    "Competitive Matrix",
    "References",
]
SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+(.+?)\s*$")
WORD_PATTERN = re.compile(r"[\w]+", re.UNICODE)


@dataclass(frozen=True)
class EvalCase:
    query: str
    min_findings: int = 1
    min_matrix_rows: int = 1
    min_references: int = 2


class EvalConfigError(ValueError):
    pass


BENCHMARK_CASES = [
    "Compare Cursor, OpenCode, and GitHub Copilot",
    "Analyze AI coding agents market positioning",
    "Compare Claude Code, Codeium, and Windsurf",
]
DEFAULT_EVAL_CASES = [EvalCase(query=query) for query in BENCHMARK_CASES]


@contextmanager
def offline_environment() -> Iterable[None]:
    previous_values = {name: os.environ.get(name) for name in OFFLINE_ENV_VARS}
    try:
        for name in OFFLINE_ENV_VARS:
            os.environ.pop(name, None)
        yield
    finally:
        for name, value in previous_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def build_eval_payload(
    cases: list[EvalCase | str] | None = None,
    run_research_func: Callable[[str], GraphState] = run_research,
) -> dict[str, Any]:
    eval_cases = [_coerce_eval_case(case) for case in (cases or DEFAULT_EVAL_CASES)]
    case_results = [_run_case(case, run_research_func) for case in eval_cases]
    return {"cases": case_results, "summary": _build_summary(case_results)}


def build_benchmark_payload(
    cases: list[str] | None = None,
    run_research_func: Callable[[str], GraphState] = run_research,
) -> dict[str, Any]:
    return build_eval_payload(cases, run_research_func=run_research_func)


def load_eval_cases(path: Path | str) -> list[EvalCase]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalConfigError("case file could not be loaded") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise EvalConfigError("case file must contain a cases list")
    return [_eval_case_from_payload(item) for item in payload["cases"]]


def _eval_case_from_payload(item: object) -> EvalCase:
    if not isinstance(item, dict):
        raise EvalConfigError("each case must be an object")
    query = item.get("query")
    if not isinstance(query, str) or not query.strip():
        raise EvalConfigError("each case must include a non-empty query")
    return EvalCase(
        query=query.strip(),
        min_findings=_optional_non_negative_int(item, "min_findings", 1),
        min_matrix_rows=_optional_non_negative_int(item, "min_matrix_rows", 1),
        min_references=_optional_non_negative_int(item, "min_references", 2),
    )


def _optional_non_negative_int(
    item: dict[str, Any],
    key: str,
    default: int,
) -> int:
    value = item.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise EvalConfigError(f"{key} must be a non-negative integer")
    return value


def _coerce_eval_case(case: EvalCase | str) -> EvalCase:
    if isinstance(case, EvalCase):
        return case
    return EvalCase(query=case)


def _run_case(
    case: EvalCase,
    run_research_func: Callable[[str], GraphState],
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with offline_environment():
            state = run_research_func(case.query)
    except Exception:
        duration_ms = _duration_ms_since(started)
        return _error_case_result(case.query, duration_ms)

    duration_ms = _duration_ms_since(started)
    return _case_result_from_state(case, duration_ms, state)


def _duration_ms_since(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _case_result_from_state(case: EvalCase, duration_ms: int, state: GraphState) -> dict[str, Any]:
    report_markdown = state.report_markdown or ""
    rules = _score_rules(case, state, report_markdown)
    score = _score_from_rules(rules)
    quality = build_report_quality_metrics(state, report_markdown)
    return {
        "query": case.query,
        "duration_ms": duration_ms,
        "score": score,
        "passed": score >= PASSING_SCORE,
        "rules": rules,
        "finding_count": len(state.findings),
        "competitive_matrix_row_count": len(state.competitive_matrix),
        "reference_count": count_references(report_markdown),
        "tool_call_count": len(state.tool_call_log),
        "llm_call_count": len(state.llm_call_log),
        "critique_passed": bool(state.critique and state.critique.passed),
        "report_has_competitive_matrix": "## Competitive Matrix" in report_markdown,
        "quality": quality,
    }


def _score_rules(case: EvalCase, state: GraphState, report_markdown: str) -> list[dict[str, Any]]:
    checks = {
        "critique_passed": bool(state.critique and state.critique.passed),
        "has_report": bool(report_markdown.strip()),
        "has_competitive_matrix_section": "## Competitive Matrix" in report_markdown,
        "references_meet_minimum": count_references(report_markdown) >= case.min_references,
        "findings_meet_minimum": len(state.findings) >= case.min_findings,
        "matrix_rows_meet_minimum": len(state.competitive_matrix) >= case.min_matrix_rows,
        "findings_cite_evidence": all(item.evidence_ids for item in state.findings),
        "matrix_rows_cite_evidence": all(item.evidence_ids for item in state.competitive_matrix),
    }
    points = 100 / len(RULE_IDS)
    return [
        {"id": rule_id, "passed": checks[rule_id], "points": points if checks[rule_id] else 0}
        for rule_id in RULE_IDS
    ]


def _score_from_rules(rules: list[dict[str, Any]]) -> int:
    return round(sum(float(rule["points"]) for rule in rules))


def build_report_quality_metrics(state: GraphState, report_markdown: str) -> dict[str, Any]:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    verified_ids = {item.id for item in verified_evidence}
    headings = _section_headings(report_markdown)
    required_present = [section for section in REQUIRED_REPORT_SECTIONS if section in headings]
    missing_required = [section for section in REQUIRED_REPORT_SECTIONS if section not in headings]
    unsupported_finding_count = sum(
        1
        for finding in state.findings
        if not _evidence_ids_supported(finding.evidence_ids, verified_ids)
    )
    unsupported_matrix_row_count = sum(
        1
        for row in state.competitive_matrix
        if not _evidence_ids_supported(row.evidence_ids, verified_ids)
    )
    claim_count = len(state.findings) + len(state.competitive_matrix)
    unsupported_claim_count = unsupported_finding_count + unsupported_matrix_row_count
    supported_claim_count = max(0, claim_count - unsupported_claim_count)
    unique_source_types = {item.source_type for item in verified_evidence}
    duplicate_source_rate = _duplicate_source_rate(verified_evidence)
    evidence_per_section = _evidence_per_section(state, verified_evidence)

    return {
        "section_count": len(headings),
        "required_sections_present": required_present,
        "missing_required_sections": missing_required,
        "section_coverage_score": _percentage(len(required_present), len(REQUIRED_REPORT_SECTIONS)),
        "report_word_count": len(WORD_PATTERN.findall(report_markdown)),
        "report_depth_score": _report_depth_score(report_markdown),
        "unique_source_domain_count": len({item.source_domain for item in verified_evidence}),
        "unique_source_type_count": len(unique_source_types),
        "source_diversity_score": min(100, round(len(unique_source_types) / 3 * 100)),
        "verified_evidence_count": len(verified_evidence),
        "evidence_per_section": evidence_per_section,
        "average_evidence_per_section": _average_count(evidence_per_section.values()),
        "official_source_coverage_score": _official_source_coverage_score(state),
        "unsupported_finding_count": unsupported_finding_count,
        "unsupported_matrix_row_count": unsupported_matrix_row_count,
        "unsupported_claim_count": unsupported_claim_count,
        "citation_support_score": 100
        if claim_count == 0
        else _percentage(supported_claim_count, claim_count),
        "duplicate_source_rate": duplicate_source_rate,
    }


def _empty_report_quality_metrics() -> dict[str, Any]:
    return {
        "section_count": 0,
        "required_sections_present": [],
        "missing_required_sections": list(REQUIRED_REPORT_SECTIONS),
        "section_coverage_score": 0,
        "report_word_count": 0,
        "report_depth_score": 0,
        "unique_source_domain_count": 0,
        "unique_source_type_count": 0,
        "source_diversity_score": 0,
        "verified_evidence_count": 0,
        "evidence_per_section": {},
        "average_evidence_per_section": 0,
        "official_source_coverage_score": 0,
        "unsupported_finding_count": 0,
        "unsupported_matrix_row_count": 0,
        "unsupported_claim_count": 0,
        "citation_support_score": 0,
        "duplicate_source_rate": 0,
    }


def _section_headings(report_markdown: str) -> list[str]:
    return [
        match.group(1).strip().rstrip("#").strip()
        for match in SECTION_HEADING_PATTERN.finditer(report_markdown)
    ]


def _evidence_ids_supported(evidence_ids: list[str], verified_ids: set[str]) -> bool:
    return bool(evidence_ids) and all(evidence_id in verified_ids for evidence_id in evidence_ids)


def _percentage(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 100
    return round(numerator / denominator * 100)


def _report_depth_score(report_markdown: str) -> int:
    word_count = len(WORD_PATTERN.findall(report_markdown))
    return min(100, round(word_count / 250 * 100))


def _duplicate_source_rate(evidence: list[Any]) -> int:
    if not evidence:
        return 0
    urls = [item.source_url for item in evidence]
    duplicate_count = len(urls) - len(set(urls))
    return _percentage(duplicate_count, len(urls))


def _evidence_per_section(
    state: GraphState,
    verified_evidence: list[Any],
) -> dict[str, int]:
    section_ids = [
        str(section.get("section_id", ""))
        for section in state.section_research_plan
        if isinstance(section.get("section_id"), str) and section.get("section_id")
    ]
    counts = {section_id: 0 for section_id in section_ids}
    for item in verified_evidence:
        section_id = item.section_id
        if section_id is None:
            continue
        counts[section_id] = counts.get(section_id, 0) + 1
    return counts


def _average_count(values: Iterable[int]) -> int:
    values = list(values)
    if not values:
        return 0
    return round(sum(values) / len(values))


def _official_source_coverage_score(state: GraphState) -> int:
    required_count = 0
    covered_count = 0
    for status in state.section_collection_status:
        required = _string_list(status.get("required_source_types", []))
        covered = set(_string_list(status.get("covered_source_types", [])))
        required_count += len(required)
        covered_count += sum(1 for source_type in required if source_type in covered)
    return _percentage(covered_count, required_count)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _error_case_result(query: str, duration_ms: int) -> dict[str, Any]:
    rules = [{"id": rule_id, "passed": False, "points": 0} for rule_id in RULE_IDS]
    return {
        "query": query,
        "duration_ms": duration_ms,
        "score": 0,
        "passed": False,
        "rules": rules,
        "finding_count": 0,
        "competitive_matrix_row_count": 0,
        "reference_count": 0,
        "tool_call_count": 0,
        "llm_call_count": 0,
        "critique_passed": False,
        "report_has_competitive_matrix": False,
        "quality": _empty_report_quality_metrics(),
        "error": SAFE_WORKFLOW_ERROR,
    }


def count_references(report_markdown: str) -> int:
    references_start = report_markdown.find("## References")
    if references_start == -1:
        return 0
    references_section = report_markdown[references_start:]
    return len(REFERENCE_LINE_PATTERN.findall(references_section))


def _build_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    failed_rules = _failed_rule_counts(case_results)
    total_score = sum(int(item["score"]) for item in case_results)
    case_count = len(case_results)
    return {
        "case_count": case_count,
        "average_score": round(total_score / case_count) if case_count else 0,
        "passed_count": sum(1 for item in case_results if item["passed"]),
        "failed_count": sum(1 for item in case_results if not item["passed"]),
        "failed_rules": failed_rules,
        "total_duration_ms": sum(int(item["duration_ms"]) for item in case_results),
        "all_critique_passed": all(bool(item["critique_passed"]) for item in case_results),
        "total_findings": sum(int(item["finding_count"]) for item in case_results),
        "total_competitive_matrix_rows": sum(
            int(item["competitive_matrix_row_count"]) for item in case_results
        ),
        "total_references": sum(int(item["reference_count"]) for item in case_results),
        "total_tool_calls": sum(int(item["tool_call_count"]) for item in case_results),
        "total_llm_calls": sum(int(item["llm_call_count"]) for item in case_results),
        "average_section_coverage_score": _average_quality(
            case_results, "section_coverage_score"
        ),
        "average_report_depth_score": _average_quality(case_results, "report_depth_score"),
        "average_source_diversity_score": _average_quality(
            case_results, "source_diversity_score"
        ),
        "average_evidence_per_section": _average_quality(
            case_results, "average_evidence_per_section"
        ),
        "average_official_source_coverage_score": _average_quality(
            case_results, "official_source_coverage_score"
        ),
        "average_citation_support_score": _average_quality(
            case_results, "citation_support_score"
        ),
        "total_unsupported_claims": sum(
            int(item.get("quality", {}).get("unsupported_claim_count", 0))
            for item in case_results
        ),
        "average_duplicate_source_rate": _average_quality(case_results, "duplicate_source_rate"),
    }


def _failed_rule_counts(case_results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in case_results:
        for rule in item.get("rules", []):
            if not rule["passed"]:
                counts[rule["id"]] = counts.get(rule["id"], 0) + 1
    return counts


def _average_quality(case_results: list[dict[str, Any]], key: str) -> int:
    if not case_results:
        return 0
    return round(
        sum(int(item.get("quality", {}).get(key, 0)) for item in case_results) / len(case_results)
    )


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# InsightGraph Eval Bench",
        "",
        "| Query | Score | Passed | Duration ms | Findings | Matrix rows | References "
        "| Tool calls | LLM calls | Critique passed | Matrix section |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for item in payload["cases"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(str(item["query"])),
                    str(item["score"]),
                    _format_bool(bool(item["passed"])),
                    str(item["duration_ms"]),
                    str(item["finding_count"]),
                    str(item["competitive_matrix_row_count"]),
                    str(item["reference_count"]),
                    str(item["tool_call_count"]),
                    str(item["llm_call_count"]),
                    _format_bool(bool(item["critique_passed"])),
                    _format_bool(bool(item["report_has_competitive_matrix"])),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Report Quality",
            "",
            "| Query | Section coverage | Report depth | Source diversity | Citation support "
            "| Evidence/section | Official source coverage | Unsupported claims "
            "| Duplicate source rate |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in payload["cases"]:
        quality = item.get("quality", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(str(item["query"])),
                    str(quality.get("section_coverage_score", 0)),
                    str(quality.get("report_depth_score", 0)),
                    str(quality.get("source_diversity_score", 0)),
                    str(quality.get("citation_support_score", 0)),
                    str(quality.get("average_evidence_per_section", 0)),
                    str(quality.get("official_source_coverage_score", 0)),
                    str(quality.get("unsupported_claim_count", 0)),
                    str(quality.get("duplicate_source_rate", 0)),
                ]
            )
            + " |"
        )

    summary = payload["summary"]
    lines.extend(
        [
            "",
            "## Summary",
            "",
            "| Cases | Average score | Passed | Failed | Total duration ms | Total findings "
            "| Total matrix rows | Total references | Total tool calls | Total LLM calls |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            "| "
            + " | ".join(
                [
                    str(summary["case_count"]),
                    str(summary["average_score"]),
                    str(summary["passed_count"]),
                    str(summary["failed_count"]),
                    str(summary["total_duration_ms"]),
                    str(summary["total_findings"]),
                    str(summary["total_competitive_matrix_rows"]),
                    str(summary["total_references"]),
                    str(summary["total_tool_calls"]),
                    str(summary["total_llm_calls"]),
                ]
            )
            + " |",
        ]
    )
    lines.extend(
        [
            "",
            "## Report Quality Summary",
            "",
            "| Avg section coverage | Avg report depth | Avg source diversity "
            "| Avg citation support | Avg evidence/section | Avg official source coverage "
            "| Unsupported claims | Avg duplicate source rate |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            "| "
            + " | ".join(
                [
                    str(summary.get("average_section_coverage_score", 0)),
                    str(summary.get("average_report_depth_score", 0)),
                    str(summary.get("average_source_diversity_score", 0)),
                    str(summary.get("average_citation_support_score", 0)),
                    str(summary.get("average_evidence_per_section", 0)),
                    str(summary.get("average_official_source_coverage_score", 0)),
                    str(summary.get("total_unsupported_claims", 0)),
                    str(summary.get("average_duplicate_source_rate", 0)),
                ]
            )
            + " |",
        ]
    )
    lines.extend(_format_failed_rule_lines(summary["failed_rules"]))
    error_lines = _format_error_lines(payload["cases"])
    if error_lines:
        lines.extend(error_lines)
    return "\n".join(lines) + "\n"


def _format_failed_rule_lines(failed_rules: dict[str, int]) -> list[str]:
    if not failed_rules:
        return []
    lines = ["", "## Failed Rules", "", "| Rule | Count |", "| --- | ---: |"]
    for rule_id, count in sorted(failed_rules.items()):
        lines.append(f"| {rule_id} | {count} |")
    return lines


def _format_error_lines(case_results: list[dict[str, Any]]) -> list[str]:
    errors = [item for item in case_results if "error" in item]
    if not errors:
        return []
    lines = ["", "## Errors", "", "| Query | Error |", "| --- | --- |"]
    for item in errors:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(str(item["query"])),
                    _markdown_table_cell(str(item["error"])),
                ]
            )
            + " |"
        )
    return lines


def _markdown_table_cell(value: str) -> str:
    return " ".join(value.replace("|", r"\|").splitlines())


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run offline InsightGraph eval bench.")
    parser.add_argument("--markdown", action="store_true", help="Print Markdown instead of JSON.")
    parser.add_argument("--output", help="Write output to a file instead of stdout.")
    parser.add_argument("--case-file", help="Load eval cases from a JSON file.")
    parser.add_argument(
        "--min-score",
        type=float,
        help="Fail when average score is below this value.",
    )
    parser.add_argument(
        "--min-section-coverage",
        type=float,
        help="Fail when average section coverage is below this value.",
    )
    parser.add_argument(
        "--min-citation-support",
        type=float,
        help="Fail when average citation support is below this value.",
    )
    parser.add_argument(
        "--min-official-source-coverage",
        type=float,
        help="Fail when average official source coverage is below this value.",
    )
    parser.add_argument(
        "--min-source-diversity",
        type=float,
        help="Fail when average source diversity is below this value.",
    )
    parser.add_argument(
        "--min-report-depth",
        type=float,
        help="Fail when average report depth is below this value.",
    )
    parser.add_argument(
        "--min-evidence-per-section",
        type=float,
        help="Fail when average evidence per section is below this value.",
    )
    parser.add_argument(
        "--max-unsupported-claims",
        type=int,
        help="Fail when unsupported claims exceed this value.",
    )
    parser.add_argument(
        "--max-duplicate-source-rate",
        type=float,
        help="Fail when average duplicate source rate exceeds this value.",
    )
    parser.add_argument(
        "--fail-on-case-failure",
        action="store_true",
        help="Fail when any eval case fails.",
    )
    args = parser.parse_args(argv)
    try:
        cases = load_eval_cases(args.case_file) if args.case_file else None
    except EvalConfigError as exc:
        print(f"Eval config error: {exc}", file=sys.stderr)
        return 2

    payload = build_eval_payload(cases) if cases is not None else build_eval_payload()
    output = (
        format_markdown(payload)
        if args.markdown
        else json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")

    gate_failures = _gate_failures(
        payload,
        min_score=args.min_score,
        min_section_coverage=args.min_section_coverage,
        min_citation_support=args.min_citation_support,
        min_official_source_coverage=args.min_official_source_coverage,
        min_source_diversity=args.min_source_diversity,
        min_report_depth=args.min_report_depth,
        min_evidence_per_section=args.min_evidence_per_section,
        max_unsupported_claims=args.max_unsupported_claims,
        max_duplicate_source_rate=args.max_duplicate_source_rate,
        fail_on_case_failure=args.fail_on_case_failure,
    )
    for failure in gate_failures:
        print(failure, file=sys.stderr)
    return 1 if gate_failures else 0


def _gate_failures(
    payload: dict[str, Any],
    *,
    min_score: float | None,
    min_section_coverage: float | None,
    min_citation_support: float | None,
    min_official_source_coverage: float | None,
    min_source_diversity: float | None,
    min_report_depth: float | None,
    min_evidence_per_section: float | None,
    max_unsupported_claims: int | None,
    max_duplicate_source_rate: float | None,
    fail_on_case_failure: bool,
) -> list[str]:
    failures: list[str] = []
    summary = payload["summary"]
    average_score = float(summary["average_score"])
    if min_score is not None and average_score < min_score:
        average = _format_number(average_score)
        threshold = _format_number(min_score)
        failures.append(
            f"Eval gate failed: average score {average} < {threshold}"
        )
    _add_minimum_gate_failure(
        failures,
        summary,
        key="average_section_coverage_score",
        label="average section coverage",
        threshold=min_section_coverage,
    )
    _add_minimum_gate_failure(
        failures,
        summary,
        key="average_citation_support_score",
        label="average citation support",
        threshold=min_citation_support,
    )
    _add_minimum_gate_failure(
        failures,
        summary,
        key="average_official_source_coverage_score",
        label="average official source coverage",
        threshold=min_official_source_coverage,
    )
    _add_minimum_gate_failure(
        failures,
        summary,
        key="average_source_diversity_score",
        label="average source diversity",
        threshold=min_source_diversity,
    )
    _add_minimum_gate_failure(
        failures,
        summary,
        key="average_report_depth_score",
        label="average report depth",
        threshold=min_report_depth,
    )
    _add_minimum_gate_failure(
        failures,
        summary,
        key="average_evidence_per_section",
        label="average evidence per section",
        threshold=min_evidence_per_section,
    )
    if max_unsupported_claims is not None:
        unsupported_claims = int(summary.get("total_unsupported_claims", 0))
        if unsupported_claims > max_unsupported_claims:
            failures.append(
                "Eval gate failed: "
                f"unsupported claims {unsupported_claims} > {max_unsupported_claims}"
            )
    _add_maximum_gate_failure(
        failures,
        summary,
        key="average_duplicate_source_rate",
        label="average duplicate source rate",
        threshold=max_duplicate_source_rate,
    )
    failed_count = int(summary["failed_count"])
    if fail_on_case_failure and failed_count > 0:
        failures.append(f"Eval gate failed: {failed_count} case(s) failed")
    return failures


def _add_minimum_gate_failure(
    failures: list[str],
    summary: dict[str, Any],
    *,
    key: str,
    label: str,
    threshold: float | None,
) -> None:
    if threshold is None:
        return
    actual = float(summary.get(key, 0))
    if actual < threshold:
        failures.append(
            f"Eval gate failed: {label} {_format_number(actual)} < {_format_number(threshold)}"
        )


def _add_maximum_gate_failure(
    failures: list[str],
    summary: dict[str, Any],
    *,
    key: str,
    label: str,
    threshold: float | None,
) -> None:
    if threshold is None:
        return
    actual = float(summary.get(key, 0))
    if actual > threshold:
        failures.append(
            f"Eval gate failed: {label} {_format_number(actual)} > {_format_number(threshold)}"
        )


def _format_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
