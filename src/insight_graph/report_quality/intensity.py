from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class ReportIntensity(StrEnum):
    concise = "concise"
    standard = "standard"
    deep = "deep"


@dataclass(frozen=True)
class ReportIntensityConfig:
    name: str
    label: str
    search_limit: int
    max_tool_calls: int
    max_fetches: int
    max_evidence_per_run: int
    max_tokens: int
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
        target_words=800,
        min_verified_evidence=5,
    ),
    ReportIntensity.standard: ReportIntensityConfig(
        name="standard",
        label="标准版",
        search_limit=12,
        max_tool_calls=40,
        max_fetches=20,
        max_evidence_per_run=40,
        max_tokens=500_000,
        target_words=1_500,
        min_verified_evidence=8,
    ),
    ReportIntensity.deep: ReportIntensityConfig(
        name="deep",
        label="高强度版",
        search_limit=15,
        max_tool_calls=80,
        max_fetches=40,
        max_evidence_per_run=80,
        max_tokens=1_000_000,
        target_words=2_500,
        min_verified_evidence=14,
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
    }
    for name, env_value in defaults.items():
        if overwrite:
            os.environ[name] = env_value
        else:
            os.environ.setdefault(name, env_value)
