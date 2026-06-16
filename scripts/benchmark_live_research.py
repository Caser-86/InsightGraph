import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from insight_graph.cli import LIVE_RESEARCH_PRESET_DEFAULTS, ResearchPreset, _apply_research_preset
from insight_graph.graph import run_research
from insight_graph.state import GraphState

DEFAULT_CASES = [
    "Compare Cursor, OpenCode, and GitHub Copilot",
    "Analyze AI coding agents market positioning",
]


def build_live_benchmark_payload(
    cases: list[str | dict[str, Any]] | None = None,
    *,
    run_research_func: Callable[[str], GraphState] = run_research,
) -> dict[str, Any]:
    previous_env = {name: os.environ.get(name) for name in LIVE_RESEARCH_PRESET_DEFAULTS}
    try:
        _apply_research_preset(ResearchPreset.live_research)
        case_results = [_run_case(case, run_research_func) for case in (cases or DEFAULT_CASES)]
    finally:
        _restore_env(previous_env)
    return {
        "preset": ResearchPreset.live_research.value,
        "cases": case_results,
        "summary": {
            "case_count": len(case_results),
            "total_runtime_ms": sum(int(item["runtime_ms"]) for item in case_results),
            "total_llm_calls": sum(int(item["llm_call_count"]) for item in case_results),
            "total_tool_calls": sum(int(item["tool_call_count"]) for item in case_results),
            "total_tokens": sum(int(item["total_tokens"]) for item in case_results),
            "average_url_validation_rate": _average_metric(
                case_results,
                "url_validation_rate",
            ),
            "average_citation_precision_proxy": _average_metric(
                case_results,
                "citation_precision_proxy",
            ),
            "average_report_depth_words": _average_metric(
                case_results,
                "report_depth_words",
            ),
            "average_section_coverage": _average_metric(case_results, "section_coverage"),
        },
    }


def _restore_env(previous_env: dict[str, str | None]) -> None:
    for name, value in previous_env.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def _run_case(
    case: str | dict[str, Any],
    run_research_func: Callable[[str], GraphState],
) -> dict[str, Any]:
    profile = _case_profile(case)
    query = profile["query"]
    started = time.perf_counter()
    state = run_research_func(query)
    runtime_ms = round((time.perf_counter() - started) * 1000)
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    valid_url_count = sum(1 for item in verified_evidence if item.reachable is not False)
    supported_citations = [
        item for item in state.citation_support if item.get("support_status") == "supported"
    ]
    citation_total = len(state.citation_support)
    expected_sections = _string_list(profile.get("expected_sections", []))
    present_sections = _present_sections(expected_sections, state.report_markdown or "")
    result = {
        "query": query,
        "runtime_ms": runtime_ms,
        "url_validity_count": valid_url_count,
        "url_validation_rate": 100
        if not verified_evidence
        else round(valid_url_count / len(verified_evidence) * 100),
        "citation_precision_proxy": 100
        if citation_total == 0
        else round(len(supported_citations) / citation_total * 100),
        "source_diversity_count": len({item.source_type for item in verified_evidence}),
        "source_diversity_by_type": _source_diversity_by_type(verified_evidence),
        "source_diversity_by_domain": _source_diversity_by_domain(verified_evidence),
        "report_depth_words": len(re.findall(r"[\w]+", state.report_markdown or "")),
        "section_coverage": 100
        if not expected_sections
        else round(len(present_sections) / len(expected_sections) * 100),
        "expected_sections_present": present_sections,
        "expected_sections_missing": [
            section for section in expected_sections if section not in present_sections
        ],
        "llm_call_count": len(state.llm_call_log),
        "tool_call_count": len(state.tool_call_log),
        "total_tokens": sum(int(record.total_tokens or 0) for record in state.llm_call_log),
    }
    result.update({key: value for key, value in profile.items() if key != "query"})
    return result


def _case_profile(case: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(case, str):
        return {"query": case}
    return {
        "case_id": str(case.get("id", "")),
        "query": str(case.get("query", "")),
        "expected_sections": _string_list(case.get("expected_sections", [])),
        "required_source_types": _string_list(case.get("required_source_types", [])),
        "minimum_source_diversity": int(case.get("minimum_source_diversity", 0)),
        "report_depth_target_words": int(case.get("report_depth_target_words", 0)),
    }


def _average_metric(case_results: list[dict[str, Any]], key: str) -> int:
    if not case_results:
        return 0
    return round(sum(int(item.get(key, 0)) for item in case_results) / len(case_results))


def _source_diversity_by_type(evidence: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in evidence:
        counts[item.source_type] = counts.get(item.source_type, 0) + 1
    return dict(sorted(counts.items()))


def _source_diversity_by_domain(evidence: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in evidence:
        domain = urlparse(item.source_url).netloc or item.source_url
        counts[domain] = counts.get(domain, 0) + 1
    return dict(sorted(counts.items()))


def _present_sections(expected_sections: list[str], report_markdown: str) -> list[str]:
    return [section for section in expected_sections if f"## {section}" in report_markdown]


def load_case_profiles(path: Path | str) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("case profile file must contain cases")
    return [case for case in payload["cases"] if isinstance(case, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def main(
    argv: list[str] | None = None,
    *,
    run_research_func: Callable[[str], GraphState] = run_research,
) -> int:
    parser = argparse.ArgumentParser(description="Run opt-in live InsightGraph benchmark.")
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Allow live network/LLM benchmark.",
    )
    parser.add_argument("--output", required=True, help="Write JSON artifact to this path.")
    parser.add_argument("--case", action="append", dest="cases", help="Benchmark case query.")
    parser.add_argument("--case-file", help="Load benchmark case profiles from JSON.")
    parser.add_argument(
        "--expected-section",
        action="append",
        dest="expected_sections",
        help="Expected section for --case queries.",
    )
    args = parser.parse_args(argv)

    allow_live = args.allow_live or os.environ.get("INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK") == "1"
    if not allow_live:
        return 2

    cases = load_case_profiles(args.case_file) if args.case_file else args.cases
    if cases and args.expected_sections and not args.case_file:
        cases = [
            {"query": query, "expected_sections": args.expected_sections}
            for query in cases
            if isinstance(query, str)
        ]
    payload = build_live_benchmark_payload(cases, run_research_func=run_research_func)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
