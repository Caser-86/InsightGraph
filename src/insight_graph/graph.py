import os
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from insight_graph.agents.analyst import analyze_evidence
from insight_graph.agents.collector import collect_evidence
from insight_graph.agents.critic import critique_analysis
from insight_graph.agents.planner import plan_research
from insight_graph.agents.reporter import write_report
from insight_graph.memory.writeback import write_report_memories
from insight_graph.persistence.checkpoints import CheckpointRecord, CheckpointStore
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
    if state.iterations >= _max_research_retries():
        return "reporter"
    return "record_retry"


def _record_retry(state: GraphState) -> GraphState:
    state.iterations = min(state.iterations + 1, _max_research_retries())
    return state


def _max_research_retries() -> int:
    raw = os.environ.get("INSIGHT_GRAPH_MAX_RESEARCH_RETRIES", "1").strip()
    try:
        value = int(raw)
    except ValueError:
        return 1
    return value if value >= 0 else 1


def run_research(user_request: str) -> GraphState:
    compiled = build_graph()
    result = compiled.invoke(GraphState(user_request=user_request))
    if isinstance(result, GraphState):
        write_report_memories(result)
        return result
    state = GraphState.model_validate(result)
    write_report_memories(state)
    return state


def run_research_with_events(
    user_request: str,
    emit_event: ResearchEventEmitter,
    *,
    run_id: str | None = None,
    checkpoint_store: CheckpointStore | None = None,
    resume: bool = False,
) -> GraphState:
    resume_stage: str | None = None
    if checkpoint_store is not None:
        checkpoint_store.ensure_schema()
        if resume and run_id is not None:
            checkpoint = checkpoint_store.load_checkpoint(run_id)
            if checkpoint is not None:
                state = checkpoint.to_state()
                resume_stage = checkpoint.node_name
                emit_event(
                    {
                        "type": "resumed_from_checkpoint",
                        "stage": resume_stage,
                        "trace_id": state.trace_id,
                    }
                )
            else:
                state = GraphState(user_request=user_request)
        else:
            state = GraphState(user_request=user_request)
    else:
        state = GraphState(user_request=user_request)

    skip_until = _next_stage_after_checkpoint(resume_stage, state)
    while True:
        if skip_until == "reporter":
            break
        if skip_until in {None, "planner"}:
            state = _run_stage_with_events(
                "planner", plan_research, state, emit_event, run_id, checkpoint_store
            )
        if skip_until in {None, "planner", "collector"}:
            state = _run_stage_with_events(
                "collector", collect_evidence, state, emit_event, run_id, checkpoint_store
            )
        if skip_until in {None, "planner", "collector", "analyst"}:
            state = _run_stage_with_events(
                "analyst", analyze_evidence, state, emit_event, run_id, checkpoint_store
            )
        if skip_until != "record_retry":
            state = _run_stage_with_events(
                "critic", critique_analysis, state, emit_event, run_id, checkpoint_store
            )
        skip_until = None
        if _route_after_critic(state) == "reporter":
            break
        state = _run_stage_with_events(
            "record_retry", _record_retry, state, emit_event, run_id, checkpoint_store
        )

    state = _run_stage_with_events(
        "reporter", write_report, state, emit_event, run_id, checkpoint_store
    )
    write_report_memories(state, run_id=run_id)
    emit_event({"type": "report_ready", "trace_id": state.trace_id})
    return state


def _next_stage_after_checkpoint(stage: str | None, state: GraphState) -> str | None:
    if stage == "critic":
        return "reporter" if _route_after_critic(state) == "reporter" else "record_retry"
    return {
        None: None,
        "planner": "collector",
        "collector": "analyst",
        "analyst": "critic",
        "record_retry": "planner",
        "reporter": "reporter",
    }.get(stage)


def _run_stage_with_events(
    stage: str,
    func: Callable[[GraphState], GraphState],
    state: GraphState,
    emit_event: ResearchEventEmitter,
    run_id: str | None = None,
    checkpoint_store: CheckpointStore | None = None,
) -> GraphState:
    tool_call_count = len(state.tool_call_log)
    llm_call_count = len(state.llm_call_log)
    emit_event({"type": "stage_started", "stage": stage, "trace_id": state.trace_id})
    state = func(state)
    for record in state.tool_call_log[tool_call_count:]:
        emit_event(
            {
                "type": "tool_call",
                "record": record.model_dump(mode="json"),
                "trace_id": state.trace_id,
            }
        )
    for record in state.llm_call_log[llm_call_count:]:
        emit_event(
            {
                "type": "llm_call",
                "record": record.model_dump(mode="json"),
                "trace_id": state.trace_id,
            }
        )
    if run_id is not None and checkpoint_store is not None:
        checkpoint_store.save_checkpoint(CheckpointRecord.from_state(run_id, stage, state))
    emit_event({"type": "stage_finished", "stage": stage, "trace_id": state.trace_id})
    return state
