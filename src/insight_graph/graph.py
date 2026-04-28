from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from insight_graph.agents.analyst import analyze_evidence
from insight_graph.agents.collector import collect_evidence
from insight_graph.agents.critic import critique_analysis
from insight_graph.agents.planner import plan_research
from insight_graph.agents.reporter import write_report
from insight_graph.state import GraphState

ResearchEventEmitter = Callable[[dict[str, Any]], None]


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("planner", plan_research)
    graph.add_node("collector", collect_evidence)
    graph.add_node("analyst", analyze_evidence)
    graph.add_node("critic", critique_analysis)
    graph.add_node("record_retry", _record_retry)
    graph.add_node("reporter", write_report)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "collector")
    graph.add_edge("collector", "analyst")
    graph.add_edge("analyst", "critic")
    graph.add_conditional_edges(
        "critic",
        _route_after_critic,
        {"reporter": "reporter", "record_retry": "record_retry"},
    )
    graph.add_edge("record_retry", "planner")
    graph.add_edge("reporter", END)
    return graph.compile()


def _route_after_critic(state: GraphState) -> str:
    if state.critique is not None and state.critique.passed:
        return "reporter"
    if state.iterations >= 1:
        return "reporter"
    return "record_retry"


def _record_retry(state: GraphState) -> GraphState:
    state.iterations += 1
    return state


def run_research(user_request: str) -> GraphState:
    compiled = build_graph()
    result = compiled.invoke(GraphState(user_request=user_request))
    if isinstance(result, GraphState):
        return result
    return GraphState.model_validate(result)


def run_research_with_events(
    user_request: str,
    emit_event: ResearchEventEmitter,
) -> GraphState:
    state = GraphState(user_request=user_request)
    while True:
        state = _run_stage_with_events("planner", plan_research, state, emit_event)
        state = _run_stage_with_events("collector", collect_evidence, state, emit_event)
        state = _run_stage_with_events("analyst", analyze_evidence, state, emit_event)
        state = _run_stage_with_events("critic", critique_analysis, state, emit_event)
        if _route_after_critic(state) == "reporter":
            break
        state = _run_stage_with_events("record_retry", _record_retry, state, emit_event)

    state = _run_stage_with_events("reporter", write_report, state, emit_event)
    emit_event({"type": "report_ready"})
    return state


def _run_stage_with_events(
    stage: str,
    func: Callable[[GraphState], GraphState],
    state: GraphState,
    emit_event: ResearchEventEmitter,
) -> GraphState:
    tool_call_count = len(state.tool_call_log)
    llm_call_count = len(state.llm_call_log)
    emit_event({"type": "stage_started", "stage": stage})
    state = func(state)
    for record in state.tool_call_log[tool_call_count:]:
        emit_event({"type": "tool_call", "record": record.model_dump(mode="json")})
    for record in state.llm_call_log[llm_call_count:]:
        emit_event({"type": "llm_call", "record": record.model_dump(mode="json")})
    emit_event({"type": "stage_finished", "stage": stage})
    return state
