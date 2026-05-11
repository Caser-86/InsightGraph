import json
import os
import re
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from insight_graph.eval import build_report_quality_metrics
from insight_graph.graph import run_research
from insight_graph.llm.config import resolve_llm_config
from insight_graph.research_jobs_store import (
    ResearchJobsStoreError,
    research_jobs_backend_from_env,
    research_jobs_path_from_env,
    research_jobs_sqlite_path_from_env,
)
from insight_graph.report_quality.fact_mapping import build_fact_conclusion_mapping
from insight_graph.report_quality.intensity import (
    ReportIntensity,
    apply_report_intensity_defaults,
    get_report_intensity,
)
from insight_graph.state import GraphState, LLMCallRecord
from insight_graph.tools.search_providers import (
    get_search_quota_snapshot,
    resolve_search_providers,
)

app = typer.Typer(help="InsightGraph research workflow CLI")


def _load_local_dotenv() -> None:
    if "PYTEST_CURRENT_TEST" in os.environ:
        return
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


class ResearchPreset(StrEnum):
    offline = "offline"
    live_llm = "live-llm"
    live_research = "live-research"


LIVE_LLM_PRESET_DEFAULTS = {
    "INSIGHT_GRAPH_USE_WEB_SEARCH": "1",
    "INSIGHT_GRAPH_SEARCH_PROVIDER": "duckduckgo",
    "INSIGHT_GRAPH_RELEVANCE_FILTER": "1",
    "INSIGHT_GRAPH_RELEVANCE_JUDGE": "openai_compatible",
    "INSIGHT_GRAPH_ANALYST_PROVIDER": "llm",
    "INSIGHT_GRAPH_REPORTER_PROVIDER": "llm",
    "INSIGHT_GRAPH_REPORT_REVIEW_PROVIDER": "llm",
}

LIVE_RESEARCH_PRESET_DEFAULTS = {
    "INSIGHT_GRAPH_USE_WEB_SEARCH": "1",
    "INSIGHT_GRAPH_SEARCH_PROVIDER": "duckduckgo",
    "INSIGHT_GRAPH_SEARCH_LIMIT": "20",
    "INSIGHT_GRAPH_USE_GITHUB_SEARCH": "1",
    "INSIGHT_GRAPH_USE_NEWS_SEARCH": "1",
    "INSIGHT_GRAPH_GITHUB_PROVIDER": "live",
    "INSIGHT_GRAPH_USE_SEC_FILINGS": "1",
    "INSIGHT_GRAPH_USE_SEC_FINANCIALS": "1",
    "INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION": "1",
    "INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS": "5",
    "INSIGHT_GRAPH_MAX_TOOL_CALLS": "200",
    "INSIGHT_GRAPH_MAX_FETCHES": "80",
    "INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN": "120",
    "INSIGHT_GRAPH_REPORTER_VALIDATE_URLS": "1",
    "INSIGHT_GRAPH_RELEVANCE_FILTER": "1",
    "INSIGHT_GRAPH_RELEVANCE_JUDGE": "openai_compatible",
    "INSIGHT_GRAPH_ANALYST_PROVIDER": "llm",
    "INSIGHT_GRAPH_REPORTER_PROVIDER": "llm",
    "INSIGHT_GRAPH_REPORT_REVIEW_PROVIDER": "llm",
    "INSIGHT_GRAPH_MAX_RESEARCH_RETRIES": "2",
}


def _apply_research_preset(preset: ResearchPreset) -> None:
    if preset == ResearchPreset.offline:
        return

    defaults = (
        LIVE_RESEARCH_PRESET_DEFAULTS
        if preset == ResearchPreset.live_research
        else LIVE_LLM_PRESET_DEFAULTS
    )
    for name, value in defaults.items():
        os.environ.setdefault(name, value)


def _apply_report_intensity(intensity: ReportIntensity | None) -> None:
    if intensity is None:
        apply_report_intensity_defaults(overwrite=False)
        return
    apply_report_intensity_defaults(intensity, overwrite=True)


def _configure_output_encoding(stdout=None, stderr=None) -> None:
    for stream in (stdout or sys.stdout, stderr or sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (AttributeError, OSError, ValueError):
                pass


def _format_llm_call_log(records: list[LLMCallRecord]) -> str:
    lines = ["## LLM Call Log", ""]
    lines.extend(
        [
            "| Stage | Provider | Model | Router | Tier | Reason | Wire API | Success | "
            "Duration ms | Input tokens | Output tokens | Total tokens | Error |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    if not records:
        lines.append("")
        lines.append("No LLM calls were recorded.")
        return "\n".join(lines)

    for record in records:
        lines.append(
            "| "
            f"{_markdown_table_cell(record.stage)} | "
            f"{_markdown_table_cell(record.provider)} | "
            f"{_markdown_table_cell(record.model)} | "
            f"{_markdown_table_cell(record.router or '-')} | "
            f"{_markdown_table_cell(record.router_tier or '-')} | "
            f"{_markdown_table_cell(record.router_reason or '-')} | "
            f"{_markdown_table_cell(record.wire_api or '')} | "
            f"{str(record.success).lower()} | "
            f"{record.duration_ms} | "
            f"{_format_optional_int(record.input_tokens)} | "
            f"{_format_optional_int(record.output_tokens)} | "
            f"{_format_optional_int(record.total_tokens)} | "
            f"{_markdown_table_cell(record.error or '')} |"
        )
    return "\n".join(lines)


def _format_optional_int(value: int | None) -> str:
    return "" if value is None else str(value)


def _markdown_table_cell(value: str) -> str:
    return " ".join(value.replace("|", r"\|").splitlines())


def _build_research_json_payload(state: GraphState) -> dict[str, object]:
    quality = build_report_quality_metrics(state, state.report_markdown or "")
    return {
        "user_request": state.user_request,
        "trace_id": state.trace_id,
        "report_markdown": state.report_markdown or "",
        "findings": [finding.model_dump(mode="json") for finding in state.findings],
        "competitive_matrix": [
            row.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
            for row in state.competitive_matrix
        ],
        "critique": state.critique.model_dump(mode="json")
        if state.critique is not None
        else None,
        "tool_call_log": [
            record.model_dump(mode="json") for record in state.tool_call_log
        ],
        "llm_call_log": [record.model_dump(mode="json") for record in state.llm_call_log],
        "iterations": state.iterations,
        "evidence_pool": _build_evidence_drilldown(state),
        "global_evidence_pool": [
            _redact_payload(evidence.model_dump(mode="json", exclude_none=True))
            for evidence in state.global_evidence_pool
        ],
        "citation_support": state.citation_support,
        "url_validation": state.url_validation,
        "report_quality_review": state.report_quality_review,
        "quality": quality,
        "quality_cards": _build_quality_cards(state, quality),
        "runtime_diagnostics": _build_runtime_diagnostics(state),
    }


def _build_evidence_drilldown(state: GraphState) -> list[dict[str, object]]:
    citation_status = _citation_status_by_evidence_id(state)
    validation_status = _url_validation_status_by_evidence_id(state)
    return [
        _redact_payload(
            {
                **evidence.model_dump(mode="json", exclude_none=True),
                "citation_support_status": citation_status.get(evidence.id, "unknown"),
                "url_validation_status": validation_status.get(evidence.id, "unknown"),
            }
        )
        for evidence in state.evidence_pool
    ]


def _redact_payload(value: object) -> object:
    if isinstance(value, str):
        return _redact_sensitive_text(value)
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_payload(item) for key, item in value.items()}
    return value


def _redact_sensitive_text(value: str) -> str:
    redacted = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", value)
    for token in ("Authorization", "request-body", "Sensitive prompt"):
        redacted = redacted.replace(token, "[REDACTED]")
    return redacted


def _citation_status_by_evidence_id(state: GraphState) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for record in state.citation_support:
        status = record.get("support_status") or record.get("status") or "unknown"
        if not isinstance(status, str):
            status = "unknown"
        for evidence_id in record.get("evidence_ids", []):
            if isinstance(evidence_id, str):
                statuses[evidence_id] = status
    return statuses


def _url_validation_status_by_evidence_id(state: GraphState) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for record in state.url_validation:
        evidence_id = record.get("evidence_id")
        if isinstance(evidence_id, str):
            statuses[evidence_id] = "valid" if record.get("valid") is True else "invalid"
    return statuses


def _build_quality_cards(state: GraphState, quality: dict[str, object]) -> dict[str, object]:
    citation_summary = _citation_support_summary(state)
    fact_mapping = build_fact_conclusion_mapping(state)
    return {
        "section_coverage_score": quality.get("section_coverage_score", 0),
        "citation_support_score": quality.get("citation_support_score", 0),
        "source_diversity_score": quality.get("source_diversity_score", 0),
        "unsupported_claim_count": quality.get("unsupported_claim_count", 0),
        "citation_supported_count": citation_summary["supported_count"],
        "citation_partial_count": citation_summary["partial_count"],
        "citation_unsupported_count": citation_summary["unsupported_count"],
        "citation_supported_ratio": citation_summary["supported_ratio"],
        "fact_mapping_score": fact_mapping.get("mapping_score", 0),
        "weak_conclusion_count": fact_mapping.get("weak_conclusion_count", 0),
        "url_validation_rate": _url_validation_rate(state),
        "total_tokens": sum(record.total_tokens or 0 for record in state.llm_call_log),
        "runtime_seconds": None,
    }


def _build_runtime_diagnostics(state: GraphState) -> dict[str, object]:
    llm_config = _safe_llm_config()
    evidence = state.evidence_pool or state.global_evidence_pool
    web_search_calls = [
        record for record in state.tool_call_log if record.tool_name == "web_search"
    ]
    citation_summary = _citation_support_summary(state)
    fact_mapping = build_fact_conclusion_mapping(state)
    topic_coverage_ratio = _topic_coverage_ratio(state.section_collection_status)
    search_provider_expression = _search_provider_expression()
    resolved_search_providers = _safe_resolved_search_providers(search_provider_expression)
    return {
        "search_provider": os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock"),
        "search_provider_expression": search_provider_expression,
        "search_providers": os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDERS"),
        "resolved_search_providers": resolved_search_providers,
        "serpapi_enabled": "serpapi" in resolved_search_providers,
        "search_limit": _int_env("INSIGHT_GRAPH_SEARCH_LIMIT"),
        "use_web_search": _truthy_env("INSIGHT_GRAPH_USE_WEB_SEARCH"),
        "use_github_search": _truthy_env("INSIGHT_GRAPH_USE_GITHUB_SEARCH"),
        "use_multi_source_collection": _truthy_env(
            "INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION"
        ),
        "max_tool_calls": _int_env("INSIGHT_GRAPH_MAX_TOOL_CALLS"),
        "max_fetches": _int_env("INSIGHT_GRAPH_MAX_FETCHES"),
        "max_evidence_per_run": _int_env("INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN"),
        "analyst_provider": os.getenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "deterministic"),
        "reporter_provider": os.getenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "deterministic"),
        "report_review_provider": os.getenv(
            "INSIGHT_GRAPH_REPORT_REVIEW_PROVIDER",
            "deterministic",
        ),
        "llm_provider": llm_config.get("provider"),
        "llm_model": llm_config.get("model"),
        "llm_max_output_tokens": llm_config.get("max_output_tokens"),
        "llm_configured": bool(llm_config.get("api_key_configured")),
        "tool_call_count": len(state.tool_call_log),
        "web_search_call_count": len(web_search_calls),
        "successful_web_search_call_count": sum(
            1 for record in web_search_calls if record.success
        ),
        "llm_call_count": len(state.llm_call_log),
        "successful_llm_call_count": sum(
            1 for record in state.llm_call_log if record.success
        ),
        "evidence_count": len(evidence),
        "verified_evidence_count": sum(1 for item in evidence if item.verified),
        "topic_coverage_ratio": topic_coverage_ratio,
        "entity_collection_status": state.entity_collection_status,
        "entity_coverage_count": len(state.entity_collection_status),
        "sufficient_entity_count": sum(
            1
            for status in state.entity_collection_status
            if bool(status.get("sufficient", False))
        ),
        "collection_stop_reason": state.collection_stop_reason,
        "report_intensity": get_report_intensity().value,
        "max_research_retries": _int_env("INSIGHT_GRAPH_MAX_RESEARCH_RETRIES"),
        "single_entity_detail_mode": os.getenv(
            "INSIGHT_GRAPH_SINGLE_ENTITY_DETAIL_MODE",
            "auto",
        ),
        "citation_support_total": citation_summary["total"],
        "citation_supported_count": citation_summary["supported_count"],
        "citation_partial_count": citation_summary["partial_count"],
        "citation_unsupported_count": citation_summary["unsupported_count"],
        "citation_supported_ratio": citation_summary["supported_ratio"],
        "fact_mapping_score": fact_mapping.get("mapping_score", 0),
        "weak_conclusion_count": fact_mapping.get("weak_conclusion_count", 0),
        "mapped_conclusion_count": fact_mapping.get("mapped_conclusion_count", 0),
        "conclusion_count": fact_mapping.get("conclusion_count", 0),
        "collection_rounds": state.collection_rounds,
        "search_quota": get_search_quota_snapshot(),
        "research_jobs_backend": _safe_research_jobs_backend(),
        "research_jobs_json_path": _safe_research_jobs_json_path(),
        "research_jobs_sqlite_path": _safe_research_jobs_sqlite_path(),
        "event_retention_limit": _int_env("INSIGHT_GRAPH_RESEARCH_JOB_EVENT_LIMIT"),
    }


def _safe_llm_config() -> dict[str, object]:
    try:
        config = resolve_llm_config()
    except ValueError as exc:
        return {
            "provider": os.getenv("INSIGHT_GRAPH_LLM_PROVIDER", "openai_compatible"),
            "model": os.getenv("INSIGHT_GRAPH_LLM_MODEL"),
            "api_key_configured": False,
            "error": str(exc),
        }
    return {
        "provider": config.provider,
        "model": config.model,
        "max_output_tokens": config.max_output_tokens,
        "api_key_configured": bool(config.api_key),
    }


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def _search_provider_expression() -> str:
    providers = os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDERS", "").strip().lower()
    if providers:
        return providers
    provider = os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock").strip().lower()
    return provider or "mock"


def _safe_resolved_search_providers(expression: str) -> list[str]:
    try:
        return resolve_search_providers(expression)
    except ValueError:
        valid = {"mock", "duckduckgo", "google", "serpapi"}
        providers: list[str] = []
        for part in expression.split(","):
            name = part.strip().lower()
            if name in valid and name not in providers:
                providers.append(name)
        return providers or ["mock"]


def _safe_research_jobs_backend() -> str:
    try:
        return research_jobs_backend_from_env()
    except ResearchJobsStoreError:
        return "unknown"


def _safe_research_jobs_json_path() -> str | None:
    path = research_jobs_path_from_env()
    if path is None:
        return None
    return str(path)


def _safe_research_jobs_sqlite_path() -> str | None:
    try:
        path = research_jobs_sqlite_path_from_env()
    except ResearchJobsStoreError:
        return None
    return str(path)


def _int_env(name: str) -> int | None:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return None


def _url_validation_rate(state: GraphState) -> int:
    if not state.url_validation:
        return 100
    valid_count = sum(1 for item in state.url_validation if item.get("valid") is True)
    return round(valid_count / len(state.url_validation) * 100)


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


def _topic_coverage_ratio(statuses: list[dict[str, object]]) -> int:
    if not statuses:
        return 100
    meaningful = [
        status
        for status in statuses
        if str(status.get("section_id", "")).strip().lower() not in {"references", "sources"}
    ]
    if not meaningful:
        return 100
    sufficient = sum(1 for status in meaningful if bool(status.get("sufficient", False)))
    return round(sufficient / len(meaningful) * 100)


@app.callback()
def main() -> None:
    """InsightGraph research workflow CLI."""
    _load_local_dotenv()
    _configure_output_encoding()


@app.command()
def research(
    query: str,
    preset: Annotated[
        ResearchPreset,
        typer.Option("--preset", help="Runtime preset: offline, live-llm, or live-research."),
    ] = ResearchPreset.offline,
    show_llm_log: Annotated[
        bool,
        typer.Option(
            "--show-llm-log",
            help="Append safe LLM call metadata after the Markdown report.",
        ),
    ] = False,
    output_json: Annotated[
        bool,
        typer.Option(
            "--output-json",
            help="Print a safe structured JSON summary instead of Markdown.",
        ),
    ] = False,
    report_intensity: Annotated[
        ReportIntensity | None,
        typer.Option(
            "--report-intensity",
            help="Report strength: concise, standard, deep, or deep-plus.",
        ),
    ] = None,
) -> None:
    """Run a research workflow and print a Markdown report."""
    _load_local_dotenv()
    _apply_research_preset(preset)
    _apply_report_intensity(report_intensity)
    state = run_research(query)
    if output_json:
        typer.echo(
            json.dumps(
                _build_research_json_payload(state),
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    output = state.report_markdown or ""
    if show_llm_log:
        output = f"{output.rstrip()}\n\n{_format_llm_call_log(state.llm_call_log)}\n"
    typer.echo(output)


if __name__ == "__main__":
    app()
