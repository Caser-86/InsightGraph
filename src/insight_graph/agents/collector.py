from insight_graph.state import GraphState
from insight_graph.tools import ToolRegistry


def collect_evidence(state: GraphState) -> GraphState:
    registry = ToolRegistry()
    collected = []
    for subtask in state.subtasks:
        for tool_name in subtask.suggested_tools:
            collected.extend(registry.run(tool_name, state.user_request, subtask.id))
    state.evidence_pool = collected
    return state
