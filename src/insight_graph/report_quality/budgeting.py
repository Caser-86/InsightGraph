import os
from dataclasses import dataclass

from insight_graph.state import GraphState, LLMCallRecord


@dataclass(frozen=True)
class ResearchBudgets:
    max_tool_calls: int = 20
    max_steps: int = 10
    max_fetches: int = 10
    max_evidence_per_run: int = 20
    max_tokens: int = 50_000


def get_research_budgets() -> ResearchBudgets:
    return ResearchBudgets(
        max_tool_calls=_positive_int_env("INSIGHT_GRAPH_MAX_TOOL_CALLS", 20),
        max_steps=_positive_int_env("INSIGHT_GRAPH_MAX_STEPS", 10),
        max_fetches=_positive_int_env("INSIGHT_GRAPH_MAX_FETCHES", 10),
        max_evidence_per_run=_positive_int_env("INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN", 20),
        max_tokens=_positive_int_env("INSIGHT_GRAPH_MAX_TOKENS", 50_000),
    )


def used_llm_tokens(state: GraphState) -> int:
    return used_llm_tokens_from_records(state.llm_call_log)


def can_start_llm_call(state: GraphState) -> bool:
    return used_llm_tokens(state) < get_research_budgets().max_tokens


def used_llm_tokens_from_records(records: list[LLMCallRecord]) -> int:
    return sum(record.total_tokens or 0 for record in records)


def can_start_llm_call_from_records(records: list[LLMCallRecord]) -> bool:
    return used_llm_tokens_from_records(records) < get_research_budgets().max_tokens


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default
