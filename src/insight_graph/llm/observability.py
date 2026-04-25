from __future__ import annotations

from insight_graph.state import LLMCallRecord


def build_llm_call_record(
    *,
    stage: str,
    provider: str,
    model: str,
    success: bool,
    duration_ms: int,
    error: Exception | None = None,
    secrets: list[str | None] | None = None,
) -> LLMCallRecord:
    return LLMCallRecord(
        stage=stage,
        provider=provider,
        model=model,
        success=success,
        duration_ms=max(duration_ms, 0),
        error=_summarize_error(error, secrets or []) if error is not None else None,
    )


def _summarize_error(error: Exception, secrets: list[str | None]) -> str:
    summary = f"{type(error).__name__}: {error}"
    for secret in secrets:
        if secret:
            summary = summary.replace(secret, "[REDACTED]")
    return summary
