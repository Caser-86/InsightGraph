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


def test_max_collection_rounds_defaults_to_one(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.delenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", raising=False)

    assert executor_module._max_collection_rounds() == 1


def test_max_collection_rounds_reads_positive_integer(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", "3")

    assert executor_module._max_collection_rounds() == 3


def test_max_collection_rounds_ignores_invalid_values(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", "0")

    assert executor_module._max_collection_rounds() == 1


def test_max_tool_rounds_defaults_to_collection_rounds(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.delenv("INSIGHT_GRAPH_MAX_TOOL_ROUNDS", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", "2")

    assert executor_module._max_tool_rounds() == 2


def test_max_tool_rounds_reads_positive_integer(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOOL_ROUNDS", "3")

    assert executor_module._max_tool_rounds() == 3


def test_executor_runs_additional_tool_round_without_section_plan(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOOL_ROUNDS", "2")

    first = Evidence(
        id="first",
        subtask_id="collect",
        title="First Evidence",
        source_url="https://example.com/first",
        snippet="First evidence has enough words for relevance.",
        source_type="official_site",
        verified=True,
    )
    second = Evidence(
        id="second",
        subtask_id="collect",
        title="Second Evidence",
        source_url="https://example.com/second",
        snippet="Second evidence has enough words for relevance.",
        source_type="news",
        verified=True,
    )
    calls = 0

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            nonlocal calls
            calls += 1
            assert name == "fake"
            assert query == "query"
            assert subtask_id == "collect"
            return [first] if calls == 1 else [second]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [record.round_index for record in updated.tool_call_log] == [1, 2]
    assert {item.id for item in updated.evidence_pool} == {"first", "second"}
    assert updated.collection_stop_reason == "max_rounds"


def test_executor_stops_tool_rounds_without_section_plan_when_no_new_evidence(
    monkeypatch,
) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOOL_ROUNDS", "3")
    duplicate = Evidence(
        id="duplicate",
        subtask_id="collect",
        title="Duplicate Evidence",
        source_url="https://example.com/duplicate",
        snippet="Duplicate evidence has enough words for relevance.",
        source_type="official_site",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [duplicate]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [record.round_index for record in updated.tool_call_log] == [1, 2]
    assert updated.collection_stop_reason == "no_new_evidence"


def test_executor_deduplicates_evidence_by_canonical_url(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    first = Evidence(
        id="first",
        subtask_id="collect",
        title="First Evidence",
        source_url="https://example.com/page?utm_source=newsletter",
        canonical_url="https://example.com/page",
        snippet="First evidence has enough words for relevance.",
        verified=True,
    )
    second = Evidence(
        id="second",
        subtask_id="collect",
        title="Second Evidence",
        source_url="https://EXAMPLE.com:443/page#section",
        canonical_url="https://example.com/page",
        snippet="Second evidence has enough words for relevance.",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [first, second]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["first"]


def test_executor_runs_query_strategies_when_present(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    observed_calls = []

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            observed_calls.append((name, query, subtask_id))
            return [
                Evidence(
                    id="strategy-evidence",
                    subtask_id=subtask_id,
                    title="Strategy Evidence",
                    source_url="https://example.com/strategy",
                    snippet="Strategy evidence has enough words for relevance.",
                    verified=True,
                )
            ]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="fallback query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"] )],
        query_strategies=[
            {
                "strategy_id": "strategy-1",
                "section_id": "pricing",
                "tool_name": "strategy_tool",
                "query": "strategy query",
                "source_type": "official_site",
                "entity_names": [],
                "round": 1,
                "reason": "section_source_requirement",
            }
        ],
    )

    updated = execute_subtasks(state)

    assert observed_calls == [("strategy_tool", "strategy query", "collect")]
    assert updated.tool_call_log[0].tool_name == "strategy_tool"
    assert updated.tool_call_log[0].query == "strategy query"


def test_executor_tool_log_records_strategy_id(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return []

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
        query_strategies=[
            {
                "strategy_id": "strategy-1",
                "section_id": "pricing",
                "tool_name": "web_search",
                "query": "pricing query",
                "source_type": "official_site",
                "entity_names": [],
                "round": 1,
                "reason": "section_source_requirement",
            }
        ],
    )

    updated = execute_subtasks(state)

    assert updated.tool_call_log[0].strategy_id == "strategy-1"


def test_executor_round_summary_counts_fetch_diagnostics(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [
                Evidence(
                    id="verified",
                    subtask_id=subtask_id,
                    title="Verified",
                    source_url="https://example.com/verified",
                    snippet="Verified evidence has enough words for relevance.",
                    verified=True,
                    fetch_status="fetched",
                ),
                Evidence(
                    id="failed",
                    subtask_id=subtask_id,
                    title="Failed",
                    source_url="https://example.com/failed",
                    snippet="network: failed",
                    verified=False,
                    fetch_status="failed",
                ),
                Evidence(
                    id="empty",
                    subtask_id=subtask_id,
                    title="Empty",
                    source_url="https://example.com/empty",
                    snippet="empty",
                    verified=False,
                    fetch_status="empty",
                ),
            ]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
        query_strategies=[
            {
                "strategy_id": "strategy-1",
                "section_id": "pricing",
                "tool_name": "fake",
                "query": "pricing query",
                "source_type": "official_site",
                "entity_names": [],
                "round": 1,
                "reason": "section_source_requirement",
            }
        ],
    )

    updated = execute_subtasks(state)

    assert updated.collection_rounds[0]["query_strategy_count"] == 1
    assert updated.collection_rounds[0]["failed_fetch_count"] == 1
    assert updated.collection_rounds[0]["empty_fetch_count"] == 1
    assert updated.collection_rounds[0]["verified_evidence_count"] == 1


def test_executor_records_conversation_summary_when_compression_enabled(
    monkeypatch,
) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_CONVERSATION_COMPRESSION", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOOL_ROUNDS", "2")
    first = Evidence(
        id="first",
        subtask_id="collect",
        title="First Evidence",
        source_url="https://example.com/first",
        snippet="First evidence has enough words for relevance.",
        source_type="official_site",
        verified=True,
    )
    second = Evidence(
        id="second",
        subtask_id="collect",
        title="Second Evidence",
        source_url="https://example.com/second",
        snippet="Second evidence has enough words for relevance.",
        source_type="news",
        verified=True,
    )
    calls = 0

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            nonlocal calls
            calls += 1
            return [first] if calls == 1 else [second]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert updated.conversation_summary is not None
    assert updated.conversation_summary["evidence_count"] == 2
    assert [item["id"] for item in updated.conversation_summary["recent_evidence"]] == [
        "first",
        "second",
    ]
    assert [record["tool_name"] for record in updated.conversation_summary["tool_calls"]] == [
        "fake",
        "fake",
    ]


def test_executor_leaves_conversation_summary_empty_by_default(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.delenv("INSIGHT_GRAPH_CONVERSATION_COMPRESSION", raising=False)

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return []

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert updated.conversation_summary is None


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


def test_executor_runs_additional_round_for_insufficient_section(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", "2")
    observed_queries: list[str] = []

    official = Evidence(
        id="official",
        subtask_id="collect",
        title="Official Evidence",
        source_url="https://example.com/official",
        snippet="Official evidence has enough words for relevance.",
        source_type="official_site",
        verified=True,
    )
    news = Evidence(
        id="news",
        subtask_id="collect",
        title="News Evidence",
        source_url="https://example.com/news",
        snippet="News evidence has enough words for relevance.",
        source_type="news",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            observed_queries.append(query)
            if len(observed_queries) == 1:
                return [official]
            return [news]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="Compare AI coding agents",
        section_research_plan=[
            {
                "section_id": "market-signals",
                "title": "Market Signals",
                "questions": ["What market news exists?"],
                "required_source_types": ["official_site", "news"],
                "min_evidence": 2,
                "budget": 3,
            }
        ],
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [record.round_index for record in updated.tool_call_log] == [1, 2]
    assert "missing source types: news" in observed_queries[1]
    assert {item.id for item in updated.evidence_pool} == {"official", "news"}
    assert updated.section_collection_status[0]["sufficient"] is True
    assert updated.collection_stop_reason == "sufficient"


def test_executor_stops_when_follow_up_adds_no_new_evidence(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", "3")
    duplicate = Evidence(
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
            return [duplicate]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        section_research_plan=[
            {
                "section_id": "market-signals",
                "required_source_types": ["official_site", "news"],
                "min_evidence": 2,
                "budget": 3,
            }
        ],
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [record.round_index for record in updated.tool_call_log] == [1, 2]
    assert updated.collection_stop_reason == "no_new_evidence"


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


def test_executor_uses_replan_requests_for_retry_follow_up_query(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    previous = Evidence(
        id="official",
        subtask_id="collect",
        title="Official Evidence",
        source_url="https://example.com/official",
        snippet="Official evidence has enough words for relevance.",
        source_type="official_site",
        verified=True,
    )
    follow_up = Evidence(
        id="news",
        subtask_id="collect",
        title="News Evidence",
        source_url="https://example.com/news",
        snippet="News evidence has enough words for relevance.",
        source_type="news",
        verified=True,
    )
    observed: dict[str, str] = {}

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            observed["query"] = query
            assert name == "fake"
            assert subtask_id == "collect"
            return [follow_up]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="Compare AI coding agents",
        iterations=1,
        evidence_pool=[previous],
        global_evidence_pool=[previous],
        replan_requests=[
            {
                "type": "missing_section_evidence",
                "section_id": "market-signals",
                "missing_evidence": 1,
                "missing_source_types": ["news"],
            }
        ],
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert "Compare AI coding agents" in observed["query"]
    assert "market-signals" in observed["query"]
    assert "news" in observed["query"]
    assert "1" in observed["query"]
    assert {item.id for item in updated.evidence_pool} == {"official", "news"}
    assert updated.tool_call_log[0].query == observed["query"]


def test_executor_assigns_evidence_to_matching_sections(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    pricing = Evidence(
        id="pricing",
        subtask_id="collect",
        title="Official Pricing",
        source_url="https://example.com/pricing",
        snippet="Official pricing evidence for enterprise plans.",
        source_type="official_site",
        verified=True,
    )
    news = Evidence(
        id="launch-news",
        subtask_id="collect",
        title="Launch News",
        source_url="https://example.com/news",
        snippet="Market launch news evidence.",
        source_type="news",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [pricing, news]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        section_research_plan=[
            {
                "section_id": "pricing",
                "title": "Pricing",
                "questions": ["What pricing model is used?"],
                "required_source_types": ["official_site"],
                "min_evidence": 1,
            },
            {
                "section_id": "market-signals",
                "title": "Market Signals",
                "questions": ["What market launch news exists?"],
                "required_source_types": ["news"],
                "min_evidence": 1,
            },
        ],
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    section_ids = {item.id: item.section_id for item in updated.evidence_pool}
    assert section_ids == {"pricing": "pricing", "launch-news": "market-signals"}


def test_executor_counts_section_status_from_assigned_evidence(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    pricing = Evidence(
        id="pricing",
        subtask_id="collect",
        title="Official Pricing",
        source_url="https://example.com/pricing",
        snippet="Official pricing evidence for enterprise plans.",
        source_type="official_site",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [pricing]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        section_research_plan=[
            {
                "section_id": "pricing",
                "title": "Pricing",
                "required_source_types": ["official_site"],
                "min_evidence": 1,
            },
            {
                "section_id": "market-signals",
                "title": "Market Signals",
                "required_source_types": ["news"],
                "min_evidence": 1,
            },
        ],
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert updated.section_collection_status == [
        {
            "section_id": "pricing",
            "round": 1,
            "evidence_count": 1,
            "min_evidence": 1,
            "required_source_types": ["official_site"],
            "covered_source_types": ["official_site"],
            "missing_source_types": [],
            "sufficient": True,
            "missing_evidence": 0,
        },
        {
            "section_id": "market-signals",
            "round": 1,
            "evidence_count": 0,
            "min_evidence": 1,
            "required_source_types": ["news"],
            "covered_source_types": [],
            "missing_source_types": ["news"],
            "sufficient": False,
            "missing_evidence": 1,
        },
    ]


def make_numbered_evidence(
    prefix: str,
    count: int,
    *,
    source_type: str = "official_site",
) -> list[Evidence]:
    return [
        Evidence(
            id=f"{prefix}-{index}",
            subtask_id="collect",
            title=f"{prefix.title()} Evidence {index}",
            source_url=f"https://example.com/{prefix}/{index}",
            snippet=f"{prefix.title()} evidence {index} has enough words for scoring.",
            source_type=source_type,
            verified=True,
        )
        for index in range(count)
    ]


def test_executor_caps_evidence_per_tool(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return make_numbered_evidence("tool", 7)

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert len(updated.evidence_pool) == 5
    assert updated.tool_call_log[0].evidence_count == 7
    assert updated.tool_call_log[0].filtered_count == 2


def test_executor_stops_before_exceeding_tool_call_budget(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOOL_CALLS", "1")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return make_numbered_evidence(name, 1)

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[
            Subtask(
                id="collect",
                description="Collect",
                suggested_tools=["tool-a", "tool-b"],
            )
        ],
    )

    updated = execute_subtasks(state)

    assert [record.tool_name for record in updated.tool_call_log] == ["tool-a"]
    assert updated.collection_stop_reason == "tool_budget_exhausted"


def test_executor_uses_configured_evidence_per_run_budget(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN", "3")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return make_numbered_evidence(name, 5)

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert len(updated.evidence_pool) == 3


def test_executor_caps_evidence_per_section_budget(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return make_numbered_evidence("pricing", 3)

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        section_research_plan=[
            {
                "section_id": "pricing",
                "title": "Pricing",
                "required_source_types": ["official_site"],
                "min_evidence": 1,
                "budget": 1,
            }
        ],
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert len(updated.evidence_pool) == 1
    assert updated.evidence_pool[0].section_id == "pricing"
    assert updated.section_collection_status[0]["evidence_count"] == 1


def test_executor_caps_total_evidence_per_run(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return make_numbered_evidence(name, 5)

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[
            Subtask(
                id="collect",
                description="Collect",
                suggested_tools=["tool-a", "tool-b", "tool-c", "tool-d", "tool-e"],
            )
        ],
    )

    updated = execute_subtasks(state)

    assert len(updated.evidence_pool) == 20


def test_executor_builds_section_aware_queries_per_tool(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    observed_queries: dict[str, str] = {}

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            observed_queries[name] = query
            return [
                Evidence(
                    id=name,
                    subtask_id=subtask_id,
                    title=f"{name} Evidence",
                    source_url=f"https://example.com/{name}",
                    snippet=f"{name} evidence has enough words for scoring.",
                    source_type="github" if name == "github_search" else "news",
                    verified=True,
                )
            ]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="Compare AI coding agents",
        resolved_entities=[{"name": "Cursor"}, {"name": "GitHub Copilot"}],
        section_research_plan=[
            {
                "section_id": "developer-ecosystem",
                "title": "Developer Ecosystem",
                "questions": ["What repository and developer activity exists?"],
                "required_source_types": ["github"],
                "min_evidence": 1,
            },
            {
                "section_id": "market-news",
                "title": "Market News",
                "questions": ["What launch or market news exists?"],
                "required_source_types": ["news"],
                "min_evidence": 1,
            },
        ],
        subtasks=[
            Subtask(
                id="collect",
                description="Collect",
                suggested_tools=["github_search", "news_search"],
            )
        ],
    )

    execute_subtasks(state)

    assert "Compare AI coding agents" in observed_queries["github_search"]
    assert "Cursor" in observed_queries["github_search"]
    assert "developer-ecosystem" in observed_queries["github_search"]
    assert "repository and developer activity" in observed_queries["github_search"]
    assert "market-news" not in observed_queries["github_search"]
    assert "market-news" in observed_queries["news_search"]
    assert "launch or market news" in observed_queries["news_search"]
    assert "developer-ecosystem" not in observed_queries["news_search"]


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


def test_executor_records_empty_web_search_without_mock_fallback(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                return []
            if name == "mock_search":
                raise AssertionError("mock_search should not run")
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="Compare AI coding agents",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["web_search"])],
    )

    updated = execute_subtasks(state)

    assert updated.evidence_pool == []
    assert updated.global_evidence_pool == []
    assert [record.tool_name for record in updated.tool_call_log] == ["web_search"]
    assert updated.tool_call_log[0].success is False
    assert updated.tool_call_log[0].evidence_count == 0
    assert updated.tool_call_log[0].filtered_count == 0
    assert updated.tool_call_log[0].error == "web_search returned no live evidence"


def test_executor_records_web_search_exception_without_mock_fallback(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                raise RuntimeError("live search unavailable")
            if name == "mock_search":
                raise AssertionError("mock_search should not run")
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["web_search"])],
    )

    updated = execute_subtasks(state)

    assert updated.evidence_pool == []
    assert [record.tool_name for record in updated.tool_call_log] == ["web_search"]
    assert updated.tool_call_log[0].success is False
    assert "live search unavailable" in updated.tool_call_log[0].error


def test_executor_does_not_filter_mock_fallback_for_empty_web_search(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "1")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                return []
            if name == "mock_search":
                raise AssertionError("mock_search should not run")
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["web_search"])],
    )

    updated = execute_subtasks(state)

    assert updated.evidence_pool == []
    assert [record.tool_name for record in updated.tool_call_log] == ["web_search"]


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
