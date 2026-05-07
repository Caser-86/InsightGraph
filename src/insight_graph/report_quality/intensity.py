from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class ReportIntensity(StrEnum):
    concise = "concise"
    standard = "standard"
    deep = "deep"
    deep_plus = "deep-plus"


@dataclass(frozen=True)
class ReportIntensityConfig:
    name: str
    label: str
    search_limit: int
    max_tool_calls: int
    max_fetches: int
    max_evidence_per_run: int
    max_tokens: int
    max_output_tokens: int
    target_words: int
    min_verified_evidence: int


INTENSITY_CONFIGS = {
    ReportIntensity.concise: ReportIntensityConfig(
        name="concise",
        label="精简版",
        search_limit=6,
        max_tool_calls=24,
        max_fetches=10,
        max_evidence_per_run=24,
        max_tokens=100_000,
        max_output_tokens=8_000,
        target_words=800,
        min_verified_evidence=5,
    ),
    ReportIntensity.standard: ReportIntensityConfig(
        name="standard",
        label="标准版",
        search_limit=30,
        max_tool_calls=320,
        max_fetches=140,
        max_evidence_per_run=220,
        max_tokens=500_000,
        max_output_tokens=32_000,
        target_words=7_000,
        min_verified_evidence=18,
    ),
    ReportIntensity.deep: ReportIntensityConfig(
        name="deep",
        label="高强度版",
        search_limit=55,
        max_tool_calls=700,
        max_fetches=320,
        max_evidence_per_run=520,
        max_tokens=2_000_000,
        max_output_tokens=64_000,
        target_words=8_000,
        min_verified_evidence=24,
    ),
    ReportIntensity.deep_plus: ReportIntensityConfig(
        name="deep-plus",
        label="极限高强度版",
        search_limit=180,
        max_tool_calls=4_000,
        max_fetches=1_600,
        max_evidence_per_run=2_800,
        max_tokens=40_000_000,
        max_output_tokens=128_000,
        target_words=18_000,
        min_verified_evidence=72,
    ),
}


def get_report_intensity(value: str | ReportIntensity | None = None) -> ReportIntensity:
    raw_value = value or os.getenv("INSIGHT_GRAPH_REPORT_INTENSITY") or "standard"
    if isinstance(raw_value, ReportIntensity):
        return raw_value
    normalized = str(raw_value).strip().lower()
    try:
        return ReportIntensity(normalized)
    except ValueError as exc:
        supported = ", ".join(item.value for item in ReportIntensity)
        raise ValueError(
            f"Unknown report intensity: {raw_value}. Supported values: {supported}"
        ) from exc


def get_report_intensity_config(
    value: str | ReportIntensity | None = None,
) -> ReportIntensityConfig:
    return INTENSITY_CONFIGS[get_report_intensity(value)]


def apply_report_intensity_defaults(
    value: str | ReportIntensity | None = None,
    *,
    overwrite: bool = False,
) -> None:
    config = get_report_intensity_config(value)
    defaults = {
        "INSIGHT_GRAPH_REPORT_INTENSITY": config.name,
        "INSIGHT_GRAPH_SEARCH_LIMIT": str(config.search_limit),
        "INSIGHT_GRAPH_MAX_TOOL_CALLS": str(config.max_tool_calls),
        "INSIGHT_GRAPH_MAX_FETCHES": str(config.max_fetches),
        "INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN": str(config.max_evidence_per_run),
        "INSIGHT_GRAPH_MAX_TOKENS": str(config.max_tokens),
        "INSIGHT_GRAPH_LLM_MAX_OUTPUT_TOKENS": str(config.max_output_tokens),
    }
    for name, env_value in defaults.items():
        if overwrite:
            os.environ[name] = env_value
        else:
            os.environ.setdefault(name, env_value)
