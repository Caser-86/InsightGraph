from langgraph.graph import END, StateGraph

from insight_graph.agents.analyst import analyze_evidence
from insight_graph.agents.collector import collect_evidence
from insight_graph.agents.critic import critique_analysis
from insight_graph.agents.planner import plan_research
from insight_graph.agents.reporter import write_report
from insight_graph.state import GraphState


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("planner", plan_research)
    graph.add_node("collector", collect_evidence)
    graph.add_node("analyst", analyze_evidence)
    graph.add_node("critic", critique_analysis)
    graph.add_node("reporter", write_report)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "collector")
    graph.add_edge("collector", "analyst")
    graph.add_edge("analyst", "critic")
    graph.add_conditional_edges(
        "critic", _route_after_critic, {"reporter": "reporter", "planner": "planner"}
    )
    graph.add_edge("reporter", END)
    return graph.compile()


def _route_after_critic(state: GraphState) -> str:
    if state.critique is not None and state.critique.passed:
        return "reporter"
    if state.iterations >= 1:
        return "reporter"
    state.iterations += 1
    return "planner"


def run_research(user_request: str) -> GraphState:
    compiled = build_graph()
    result = compiled.invoke(GraphState(user_request=user_request))
    if isinstance(result, GraphState):
        return result
    return GraphState.model_validate(result)
