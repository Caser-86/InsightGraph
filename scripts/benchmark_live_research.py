import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from insight_graph.cli import LIVE_RESEARCH_PRESET_DEFAULTS, ResearchPreset, _apply_research_preset
from insight_graph.graph import run_research
from insight_graph.state import GraphState

DEFAULT_CASES = [
    "Compare Cursor, OpenCode, and GitHub Copilot",
    "Analyze AI coding agents market positioning",
]


def build_live_benchmark_payload(
    cases: list[str] | None = None,
    *,
    run_research_func: Callable[[str], GraphState] = run_research,
) -> dict[str, Any]:
    previous_env = {name: os.environ.get(name) for name in LIVE_RESEARCH_PRESET_DEFAULTS}
    try:
        _apply_research_preset(ResearchPreset.live_research)
        case_results = [_run_case(query, run_research_func) for query in (cases or DEFAULT_CASES)]
    finally:
        _restore_env(previous_env)
    return {
        "preset": ResearchPreset.live_research.value,
        "cases": case_results,
        "summary": {
            "case_count": len(case_results),
            "total_runtime_ms": sum(int(item["runtime_ms"]) for item in case_results),
            "total_llm_calls": sum(int(item["llm_call_count"]) for item in case_results),
            "total_tokens": sum(int(item["total_tokens"]) for item in case_results),
        },
    }


def _restore_env(previous_env: dict[str, str | None]) -> None:
    for name, value in previous_env.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def _run_case(
    query: str,
    run_research_func: Callable[[str], GraphState],
) -> dict[str, Any]:
    started = time.perf_counter()
    state = run_research_func(query)
    runtime_ms = round((time.perf_counter() - started) * 1000)
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    supported_citations = [
        item for item in state.citation_support if item.get("support_status") == "supported"
    ]
    citation_total = len(state.citation_support)
    return {
        "query": query,
        "runtime_ms": runtime_ms,
        "url_validity_count": sum(1 for item in verified_evidence if item.reachable is not False),
        "citation_precision_proxy": 100
        if citation_total == 0
        else round(len(supported_citations) / citation_total * 100),
        "source_diversity_count": len({item.source_type for item in verified_evidence}),
        "report_depth_words": len(re.findall(r"[\w]+", state.report_markdown or "")),
        "llm_call_count": len(state.llm_call_log),
        "tool_call_count": len(state.tool_call_log),
        "total_tokens": sum(int(record.total_tokens or 0) for record in state.llm_call_log),
    }


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
    args = parser.parse_args(argv)

    allow_live = args.allow_live or os.environ.get("INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK") == "1"
    if not allow_live:
        return 2

    payload = build_live_benchmark_payload(args.cases, run_research_func=run_research_func)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
