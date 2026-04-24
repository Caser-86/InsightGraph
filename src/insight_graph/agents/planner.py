from insight_graph.state import GraphState, Subtask


def plan_research(state: GraphState) -> GraphState:
    state.subtasks = [
        Subtask(
            id="scope",
            description="Identify key products, companies, and scope from the user request",
            subtask_type="research",
        ),
        Subtask(
            id="collect",
            description=(
                "Collect evidence about product positioning, features, pricing, and sources"
            ),
            subtask_type="research",
            dependencies=["scope"],
            suggested_tools=["mock_search"],
        ),
        Subtask(
            id="analyze",
            description="Analyze competitive patterns, differentiators, risks, and trends",
            subtask_type="synthesis",
            dependencies=["collect"],
        ),
        Subtask(
            id="report",
            description="Synthesize findings into a cited research report",
            subtask_type="synthesis",
            dependencies=["analyze"],
        ),
    ]
    return state
