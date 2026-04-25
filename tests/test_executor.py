import importlib

from insight_graph.agents.executor import execute_subtasks
from insight_graph.state import Evidence, GraphState, LLMCallRecord, Subtask


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


def test_executor_does_not_filter_when_relevance_filter_disabled(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.delenv("INSIGHT_GRAPH_RELEVANCE_FILTER", raising=False)

    unverified = Evidence(
        id="unverified",
        subtask_id="collect",
        title="Unverified",
        source_url="https://example.com/unverified",
        snippet="Unverified evidence.",
        verified=False,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [unverified]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["unverified"]
    assert updated.tool_call_log[0].filtered_count == 0


def test_executor_filters_unverified_evidence_when_enabled(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "1")

    verified = Evidence(
        id="verified",
        subtask_id="collect",
        title="Verified",
        source_url="https://example.com/verified",
        snippet="Verified evidence.",
        verified=True,
    )
    unverified = Evidence(
        id="unverified",
        subtask_id="collect",
        title="Unverified",
        source_url="https://example.com/unverified",
        snippet="Unverified evidence.",
        verified=False,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [verified, unverified]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["verified"]
    assert updated.global_evidence_pool == updated.evidence_pool
    assert updated.tool_call_log[0].evidence_count == 2
    assert updated.tool_call_log[0].filtered_count == 1


def test_executor_passes_llm_call_log_to_relevance_filter(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "1")

    evidence = Evidence(
        id="verified",
        subtask_id="collect",
        title="Verified",
        source_url="https://example.com/verified",
        snippet="Verified evidence.",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [evidence]

    def fake_filter_relevant_evidence(query, subtask, evidence, judge=None, llm_call_log=None):
        assert llm_call_log is not None
        llm_call_log.append(
            LLMCallRecord(
                stage="relevance",
                provider="openai_compatible",
                model="relay-model",
                success=True,
                duration_ms=1,
            )
        )
        return evidence, 0

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    monkeypatch.setattr(
        executor_module, "filter_relevant_evidence", fake_filter_relevant_evidence
    )
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert len(updated.llm_call_log) == 1
    assert updated.llm_call_log[0].stage == "relevance"


def test_executor_filters_after_per_tool_deduplication(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "1")

    duplicate_unverified = Evidence(
        id="duplicate",
        subtask_id="collect",
        title="Duplicate",
        source_url="https://example.com/duplicate",
        snippet="Duplicate evidence.",
        verified=False,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [duplicate_unverified, duplicate_unverified.model_copy()]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert updated.evidence_pool == []
    assert updated.tool_call_log[0].evidence_count == 2
    assert updated.tool_call_log[0].filtered_count == 1
