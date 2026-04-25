from insight_graph.agents.executor import execute_subtasks
from insight_graph.state import GraphState


def collect_evidence(state: GraphState) -> GraphState:
    return execute_subtasks(state)
