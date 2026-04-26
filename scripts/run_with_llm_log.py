from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from insight_graph.state import GraphState

MAX_SLUG_LENGTH = 60


def build_log_payload(state: GraphState, *, preset: str) -> dict[str, Any]:
    return {
        "query": state.user_request,
        "preset": preset,
        "report_markdown_length": len(state.report_markdown or ""),
        "finding_count": len(state.findings),
        "competitive_matrix_row_count": len(state.competitive_matrix),
        "tool_call_log": [record.model_dump(mode="json") for record in state.tool_call_log],
        "llm_call_log": [record.model_dump(mode="json") for record in state.llm_call_log],
        "iterations": state.iterations,
    }


def slugify_query(query: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:MAX_SLUG_LENGTH]
    slug = slug.strip("-")
    return slug or "research"


def build_log_path(*, log_dir: Path, query: str, now: datetime) -> Path:
    timestamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"{timestamp}-{slugify_query(query)}"
    candidate = log_dir / f"{base_name}.json"
    suffix = 2
    while candidate.exists():
        candidate = log_dir / f"{base_name}-{suffix}.json"
        suffix += 1
    return candidate
