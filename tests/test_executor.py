import importlib

from insight_graph.agents.executor import execute_subtasks
from insight_graph.state import Evidence, GraphState, Subtask


def test_executor_collects_evidence_and_records_success() -> None:
    state = GraphState(
        user_request="Compare AI coding agents",
        subtasks=[
            Subtask(id="scope", description="Scope"),
            Subtask(
                id="collect",
                description="Collect evidence",
                suggested_tools=["mock_search"],
            ),
        ],
    )

    updated = execute_subtasks(state)

    assert len(updated.evidence_pool) == 3
    assert updated.global_evidence_pool == updated.evidence_pool
    assert len(updated.tool_call_log) == 1
    assert updated.tool_call_log[0].subtask_id == "collect"
    assert updated.tool_call_log[0].tool_name == "mock_search"
    assert updated.tool_call_log[0].query == "Compare AI coding agents"
    assert updated.tool_call_log[0].evidence_count == 3
    assert updated.tool_call_log[0].success is True
    assert updated.tool_call_log[0].error is None


def test_executor_deduplicates_evidence(monkeypatch) -> None:
    registry_module = importlib.import_module("insight_graph.agents.executor")

    duplicate = Evidence(
        id="same",
        subtask_id="collect",
        title="Same",
        source_url="https://example.com/same",
        snippet="Same evidence.",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [duplicate, duplicate.model_copy()]

    monkeypatch.setattr(registry_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert len(updated.evidence_pool) == 1
    assert updated.evidence_pool[0].id == "same"
    assert updated.tool_call_log[0].evidence_count == 2


def test_executor_logs_tool_failure_and_continues(monkeypatch) -> None:
    registry_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            raise KeyError("Unknown tool: broken")

    monkeypatch.setattr(registry_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["broken"])],
    )

    updated = execute_subtasks(state)

    assert updated.evidence_pool == []
    assert updated.global_evidence_pool == []
    assert len(updated.tool_call_log) == 1
    assert updated.tool_call_log[0].success is False
    assert updated.tool_call_log[0].evidence_count == 0
    assert "Unknown tool: broken" in updated.tool_call_log[0].error


def test_executor_appends_to_existing_tool_call_log() -> None:
    state = GraphState(
        user_request="Compare AI coding agents",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["mock_search"])],
    )
    state.tool_call_log.append(
        {
            "subtask_id": "previous",
            "tool_name": "mock_search",
            "query": "previous query",
            "evidence_count": 1,
        }
    )

    updated = execute_subtasks(state)

    assert [record.subtask_id for record in updated.tool_call_log] == ["previous", "collect"]
