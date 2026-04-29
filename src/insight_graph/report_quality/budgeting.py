import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchBudgets:
    max_tool_calls: int = 20
    max_steps: int = 10
    max_fetches: int = 10
    max_evidence_per_run: int = 20


def get_research_budgets() -> ResearchBudgets:
    return ResearchBudgets(
        max_tool_calls=_positive_int_env("INSIGHT_GRAPH_MAX_TOOL_CALLS", 20),
        max_steps=_positive_int_env("INSIGHT_GRAPH_MAX_STEPS", 10),
        max_fetches=_positive_int_env("INSIGHT_GRAPH_MAX_FETCHES", 10),
        max_evidence_per_run=_positive_int_env("INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN", 20),
    )


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default
