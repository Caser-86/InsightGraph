from insight_graph.graph import run_research, run_research_with_events
from insight_graph.persistence.checkpoints import CheckpointRecord
from insight_graph.state import Critique, GraphState


def clear_llm_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_PROVIDER",
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_LLM_BASE_URL",
        "INSIGHT_GRAPH_LLM_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.delenv(name, raising=False)


def clear_planner_tool_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_USE_WEB_SEARCH",
        "INSIGHT_GRAPH_USE_GITHUB_SEARCH",
        "INSIGHT_GRAPH_USE_NEWS_SEARCH",
        "INSIGHT_GRAPH_USE_DOCUMENT_READER",
        "INSIGHT_GRAPH_USE_READ_FILE",
        "INSIGHT_GRAPH_USE_LIST_DIRECTORY",
        "INSIGHT_GRAPH_USE_WRITE_FILE",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_run_research_executes_full_graph(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    clear_planner_tool_env(monkeypatch)

    result = run_research("Compare Cursor, OpenCode, and GitHub Copilot")

    assert result.critique is not None
    assert result.critique.passed is True
    assert result.report_markdown is not None
    assert "# InsightGraph Research Report" in result.report_markdown
    assert "## Competitive Matrix" in result.report_markdown
    assert "https://cursor.com/pricing" in result.report_markdown
    assert result.domain_profile == "competitive_intel"
    assert [entity["id"] for entity in result.resolved_entities] == [
        "cursor",
        "opencode",
        "github-copilot",
    ]
    assert result.section_research_plan
    assert result.competitive_matrix
    assert result.llm_call_log == []


def test_run_research_stops_after_failed_retry(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    clear_planner_tool_env(monkeypatch)
    import insight_graph.graph as graph_module

    def collect_no_evidence(state: GraphState) -> GraphState:
        state.evidence_pool = []
        return state

    monkeypatch.setattr(graph_module, "collect_evidence", collect_no_evidence)

    result = graph_module.run_research("Unknown product")

    assert result.critique is not None
    assert result.critique.passed is False
    assert result.iterations == 1
    assert result.report_markdown is not None
    assert "# InsightGraph Research Report" in result.report_markdown
    assert "Official sources establish baseline product positioning" not in result.report_markdown
    assert "Evidence, findings, or citation support are insufficient." in result.report_markdown


def test_run_research_with_events_emits_stage_events(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    clear_planner_tool_env(monkeypatch)
    events: list[dict[str, object]] = []

    result = run_research_with_events(
        "Compare Cursor, OpenCode, and GitHub Copilot",
        events.append,
    )

    assert result.report_markdown is not None
    assert [
        (event["type"], event.get("stage"))
        for event in events
        if event["type"] in {"stage_started", "stage_finished"}
    ] == [
        ("stage_started", "planner"),
        ("stage_finished", "planner"),
        ("stage_started", "collector"),
        ("stage_finished", "collector"),
        ("stage_started", "analyst"),
        ("stage_finished", "analyst"),
        ("stage_started", "critic"),
        ("stage_finished", "critic"),
        ("stage_started", "reporter"),
        ("stage_finished", "reporter"),
    ]


def test_run_research_with_events_emits_tool_and_report_events(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    clear_planner_tool_env(monkeypatch)
    events: list[dict[str, object]] = []

    result = run_research_with_events(
        "Compare Cursor, OpenCode, and GitHub Copilot",
        events.append,
    )

    tool_events = [event for event in events if event["type"] == "tool_call"]
    report_events = [event for event in events if event["type"] == "report_ready"]
    assert tool_events
    assert tool_events[0]["record"]["tool_name"] == "mock_search"
    assert report_events == [{"type": "report_ready"}]
    assert result.report_markdown is not None


class RecordingCheckpointStore:
    def __init__(self, loaded_record: CheckpointRecord | None = None) -> None:
        self.records: list[CheckpointRecord] = []
        self.loaded_record = loaded_record
        self.schema_calls = 0

    def ensure_schema(self) -> None:
        self.schema_calls += 1

    def save_checkpoint(self, record: CheckpointRecord) -> None:
        self.records.append(record)

    def load_checkpoint(self, run_id: str) -> CheckpointRecord | None:
        if self.loaded_record is not None and self.loaded_record.run_id == run_id:
            return self.loaded_record
        return None


def test_run_research_with_events_saves_checkpoints_after_each_stage(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    clear_planner_tool_env(monkeypatch)
    store = RecordingCheckpointStore()

    result = run_research_with_events(
        "Compare Cursor, OpenCode, and GitHub Copilot",
        lambda event: None,
        run_id="run-1",
        checkpoint_store=store,
    )

    assert store.schema_calls == 1
    assert [record.node_name for record in store.records] == [
        "planner",
        "collector",
        "analyst",
        "critic",
        "reporter",
    ]
    assert store.records[-1].run_id == "run-1"
    assert store.records[-1].to_state().report_markdown == result.report_markdown


def test_run_research_with_events_resumes_after_loaded_checkpoint(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    clear_planner_tool_env(monkeypatch)
    first_store = RecordingCheckpointStore()
    run_research_with_events(
        "Compare Cursor, OpenCode, and GitHub Copilot",
        lambda event: None,
        run_id="run-1",
        checkpoint_store=first_store,
    )
    collector_checkpoint = next(
        record for record in first_store.records if record.node_name == "collector"
    )
    resumed_store = RecordingCheckpointStore(loaded_record=collector_checkpoint)
    events: list[dict[str, object]] = []

    result = run_research_with_events(
        "ignored because checkpoint has state",
        events.append,
        run_id="run-1",
        checkpoint_store=resumed_store,
        resume=True,
    )

    assert result.user_request == "Compare Cursor, OpenCode, and GitHub Copilot"
    assert [record.node_name for record in resumed_store.records] == [
        "analyst",
        "critic",
        "reporter",
    ]
    assert events[0] == {"type": "resumed_from_checkpoint", "stage": "collector"}


def test_run_research_with_events_resumes_failed_critic_at_retry(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    clear_planner_tool_env(monkeypatch)
    failed_state = GraphState(
        user_request="Needs retry",
        critique=Critique(
            passed=False,
            issues=["Need more evidence"],
            reason="Needs another collection round.",
        ),
        iterations=0,
    )
    checkpoint = CheckpointRecord.from_state("run-1", "critic", failed_state)
    store = RecordingCheckpointStore(loaded_record=checkpoint)

    result = run_research_with_events(
        "ignored",
        lambda event: None,
        run_id="run-1",
        checkpoint_store=store,
        resume=True,
    )

    assert [record.node_name for record in store.records[:2]] == [
        "record_retry",
        "planner",
    ]
    assert result.iterations == 1


def test_run_research_with_events_resumes_passed_critic_at_reporter(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    clear_planner_tool_env(monkeypatch)
    passed_state = GraphState(
        user_request="Ready to report",
        critique=Critique(passed=True, issues=[], reason="Ready."),
    )
    checkpoint = CheckpointRecord.from_state("run-1", "critic", passed_state)
    store = RecordingCheckpointStore(loaded_record=checkpoint)

    run_research_with_events(
        "ignored",
        lambda event: None,
        run_id="run-1",
        checkpoint_store=store,
        resume=True,
    )

    assert [record.node_name for record in store.records] == ["reporter"]
