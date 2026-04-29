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


def test_executor_records_section_collection_status() -> None:
    state = GraphState(
        user_request="Compare AI coding agents",
        section_research_plan=[
            {
                "section_id": "executive-summary",
                "title": "Executive Summary",
                "questions": ["What matters?"],
                "required_source_types": ["official_site"],
                "min_evidence": 2,
                "budget": 3,
                "entity_ids": [],
            }
        ],
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["mock_search"])],
    )

    updated = execute_subtasks(state)

    assert updated.section_collection_status == [
        {
            "section_id": "executive-summary",
            "round": 1,
            "evidence_count": 3,
            "min_evidence": 2,
            "required_source_types": ["official_site"],
            "covered_source_types": ["official_site"],
            "missing_source_types": [],
            "sufficient": True,
            "missing_evidence": 0,
        }
    ]


def test_executor_marks_section_insufficient_when_required_source_type_missing(
    monkeypatch,
) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    official = Evidence(
        id="official",
        subtask_id="collect",
        title="Official Evidence",
        source_url="https://example.com/official",
        snippet="Official evidence has enough words for relevance.",
        source_type="official_site",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [official]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        section_research_plan=[
            {
                "section_id": "market-signals",
                "required_source_types": ["official_site", "news"],
                "min_evidence": 1,
            }
        ],
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert updated.section_collection_status == [
        {
            "section_id": "market-signals",
            "round": 1,
            "evidence_count": 1,
            "min_evidence": 1,
            "required_source_types": ["official_site", "news"],
            "covered_source_types": ["official_site"],
            "missing_source_types": ["news"],
            "sufficient": False,
            "missing_evidence": 0,
        }
    ]


def test_executor_records_evidence_scores() -> None:
    state = GraphState(
        user_request="Compare AI coding agents",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["mock_search"])],
    )

    updated = execute_subtasks(state)

    assert len(updated.evidence_scores) == 3
    assert updated.evidence_scores[0]["evidence_id"] == updated.evidence_pool[0].id
    assert updated.evidence_scores[0]["overall_score"] > 0


def test_executor_orders_evidence_pool_by_overall_score(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    weak = Evidence(
        id="weak",
        subtask_id="collect",
        title="Weak Evidence",
        source_url="https://example.com/weak",
        snippet="Short.",
        source_type="unknown",
        verified=True,
    )
    official = Evidence(
        id="official",
        subtask_id="collect",
        title="Official Evidence",
        source_url="https://example.com/official",
        snippet="Official evidence has enough words for relevance.",
        source_type="official_site",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [weak, official]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["official", "weak"]
    assert [item["evidence_id"] for item in updated.evidence_scores] == ["official", "weak"]


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


def test_executor_collects_multiple_suggested_tools(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    web = Evidence(
        id="web",
        subtask_id="collect",
        title="Web Evidence",
        source_url="https://example.com/web",
        snippet="Web evidence.",
        source_type="official_site",
        verified=True,
    )
    github = Evidence(
        id="github",
        subtask_id="collect",
        title="GitHub Evidence",
        source_url="https://github.com/example/project",
        snippet="GitHub evidence.",
        source_type="github",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                return [web]
            if name == "github_search":
                return [github]
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="Compare AI coding agents",
        subtasks=[
            Subtask(
                id="collect",
                description="Collect",
                suggested_tools=["web_search", "github_search"],
            )
        ],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["web", "github"]
    assert [record.tool_name for record in updated.tool_call_log] == [
        "web_search",
        "github_search",
    ]


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


def test_executor_falls_back_to_mock_search_for_empty_web_search(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    fallback = Evidence(
        id="fallback",
        subtask_id="collect",
        title="Fallback Evidence",
        source_url="https://example.com/fallback",
        snippet="Fallback evidence.",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                return []
            if name == "mock_search":
                return [fallback]
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="Compare AI coding agents",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["web_search"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["fallback"]
    assert updated.global_evidence_pool == updated.evidence_pool
    assert [record.tool_name for record in updated.tool_call_log] == [
        "web_search",
        "mock_search",
    ]
    assert updated.tool_call_log[0].success is False
    assert updated.tool_call_log[0].evidence_count == 0
    assert updated.tool_call_log[0].filtered_count == 0
    assert updated.tool_call_log[0].error == (
        "web_search returned no evidence; falling back to mock_search"
    )
    assert updated.tool_call_log[1].success is True
    assert updated.tool_call_log[1].evidence_count == 1
    assert updated.tool_call_log[1].filtered_count == 0
    assert updated.tool_call_log[1].error == "fallback for web_search"


def test_executor_falls_back_to_mock_search_for_web_search_exception(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    fallback = Evidence(
        id="fallback",
        subtask_id="collect",
        title="Fallback Evidence",
        source_url="https://example.com/fallback",
        snippet="Fallback evidence.",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                raise RuntimeError("live search unavailable")
            if name == "mock_search":
                return [fallback]
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["web_search"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["fallback"]
    assert [record.tool_name for record in updated.tool_call_log] == [
        "web_search",
        "mock_search",
    ]
    assert updated.tool_call_log[0].success is False
    assert "live search unavailable" in updated.tool_call_log[0].error
    assert updated.tool_call_log[1].success is True
    assert updated.tool_call_log[1].error == "fallback for web_search"


def test_executor_records_failed_mock_search_fallback(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                return []
            if name == "mock_search":
                raise RuntimeError("mock unavailable")
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["web_search"])],
    )

    updated = execute_subtasks(state)

    assert updated.evidence_pool == []
    assert [record.tool_name for record in updated.tool_call_log] == [
        "web_search",
        "mock_search",
    ]
    assert updated.tool_call_log[0].success is False
    assert updated.tool_call_log[1].success is False
    assert updated.tool_call_log[1].error == (
        "fallback for web_search failed: mock unavailable"
    )


def test_executor_applies_relevance_filter_to_mock_search_fallback(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "1")

    kept = Evidence(
        id="kept",
        subtask_id="collect",
        title="Kept",
        source_url="https://example.com/kept",
        snippet="Kept evidence.",
        verified=True,
    )
    dropped = Evidence(
        id="dropped",
        subtask_id="collect",
        title="Dropped",
        source_url="https://example.com/dropped",
        snippet="Dropped evidence.",
        verified=False,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                return []
            if name == "mock_search":
                return [kept, dropped]
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["web_search"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["kept"]
    assert updated.tool_call_log[1].tool_name == "mock_search"
    assert updated.tool_call_log[1].evidence_count == 2
    assert updated.tool_call_log[1].filtered_count == 1


def test_executor_keeps_successful_empty_results_for_non_web_search(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return []

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["custom_tool"])],
    )

    updated = execute_subtasks(state)

    assert updated.evidence_pool == []
    assert len(updated.tool_call_log) == 1
    assert updated.tool_call_log[0].tool_name == "custom_tool"
    assert updated.tool_call_log[0].success is True
    assert updated.tool_call_log[0].evidence_count == 0
    assert updated.tool_call_log[0].error is None


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
