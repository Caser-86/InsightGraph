from insight_graph import __version__
from insight_graph.cli import app
from insight_graph.llm import ChatCompletionResult, ChatMessage
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
    get_llm_wire_api,
)
from insight_graph.llm.router import LLMRouterDecision
from insight_graph.state import (
    CompetitiveMatrixRow,
    Evidence,
    GraphState,
    LLMCallRecord,
    Subtask,
    ToolCallRecord,
)


def test_package_version_is_defined() -> None:
    assert __version__ == "0.1.0"


def test_cli_app_is_importable() -> None:
    assert app.info.help == "InsightGraph research workflow CLI"


def test_subtask_defaults_to_research_type() -> None:
    subtask = Subtask(id="s1", description="Compare Cursor and GitHub Copilot")

    assert subtask.subtask_type == "research"
    assert subtask.dependencies == []
    assert subtask.suggested_tools == []


def test_evidence_requires_source_url() -> None:
    evidence = Evidence(
        id="e1",
        subtask_id="s1",
        title="Cursor pricing",
        source_url="https://cursor.com/pricing",
        snippet="Cursor publishes pricing tiers on its pricing page.",
        source_type="official_site",
    )

    assert evidence.verified is False
    assert evidence.source_domain == "cursor.com"


def test_evidence_stores_search_candidate_metadata() -> None:
    evidence = Evidence(
        id="e1",
        subtask_id="s1",
        title="Cursor pricing",
        source_url="https://cursor.com/pricing",
        snippet="Cursor publishes pricing tiers on its pricing page.",
        search_provider="duckduckgo",
        search_rank=2,
        search_query="cursor pricing",
        search_snippet="Search result snippet.",
        fetch_status="fetched",
        fetch_error=None,
    )

    assert evidence.search_provider == "duckduckgo"
    assert evidence.search_rank == 2
    assert evidence.search_query == "cursor pricing"
    assert evidence.search_snippet == "Search result snippet."
    assert evidence.fetch_status == "fetched"
    assert evidence.fetch_error is None


def test_evidence_stores_canonical_url() -> None:
    evidence = Evidence(
        id="e1",
        subtask_id="s1",
        title="Cursor pricing",
        source_url="https://cursor.com/pricing?utm_source=x",
        snippet="Cursor publishes pricing tiers on its pricing page.",
        canonical_url="https://cursor.com/pricing",
    )

    assert evidence.canonical_url == "https://cursor.com/pricing"


def test_evidence_stores_verification_state_metadata() -> None:
    evidence = Evidence(
        id="e1",
        subtask_id="s1",
        title="Cursor pricing",
        source_url="https://cursor.com/pricing",
        snippet="Cursor publishes pricing tiers on its pricing page.",
        reachable=True,
        source_trusted=True,
        claim_supported=None,
    )

    assert evidence.reachable is True
    assert evidence.source_trusted is True
    assert evidence.claim_supported is None


def test_graph_state_starts_with_empty_collections() -> None:
    state = GraphState(user_request="Analyze AI coding agents")

    assert state.user_request == "Analyze AI coding agents"
    assert state.subtasks == []
    assert state.evidence_pool == []
    assert state.findings == []
    assert state.competitive_matrix == []
    assert state.report_markdown is None
    assert state.memory_context == []


def test_competitive_matrix_row_stores_evidence_backed_fields() -> None:
    row = CompetitiveMatrixRow(
        product="Cursor",
        positioning="Official product positioning signal",
        strengths=["Official/documented source coverage"],
        evidence_ids=["cursor-pricing"],
    )

    assert row.product == "Cursor"
    assert row.positioning == "Official product positioning signal"
    assert row.strengths == ["Official/documented source coverage"]
    assert row.evidence_ids == ["cursor-pricing"]


def test_tool_call_record_defaults_to_success() -> None:
    record = ToolCallRecord(
        subtask_id="collect",
        tool_name="mock_search",
        query="Compare AI coding agents",
    )

    assert record.evidence_count == 0
    assert record.filtered_count == 0
    assert record.success is True
    assert record.error is None


def test_collection_depth_metadata_defaults_are_backward_compatible() -> None:
    record = ToolCallRecord(subtask_id="collect", tool_name="mock_search", query="q")
    state = GraphState(user_request="q")

    assert record.round_index == 1
    assert record.section_id is None
    assert record.stop_reason is None
    assert state.collection_rounds == []
    assert state.collection_stop_reason is None
    assert state.tried_strategies == []
    assert state.conversation_summary is None
    assert state.url_validation == []


def test_graph_state_starts_with_executor_collections() -> None:
    state = GraphState(user_request="Analyze AI coding agents")

    assert state.global_evidence_pool == []
    assert state.tool_call_log == []


def test_llm_call_record_stores_metadata_only() -> None:
    record = LLMCallRecord(
        stage="analyst",
        provider="llm",
        model="relay-model",
        success=True,
        duration_ms=12,
    )

    assert record.stage == "analyst"
    assert record.provider == "llm"
    assert record.model == "relay-model"
    assert record.success is True
    assert record.duration_ms == 12
    assert record.error is None


def test_llm_call_record_stores_nullable_token_fields() -> None:
    record = LLMCallRecord(
        stage="analyst",
        provider="llm",
        model="relay-model",
        success=True,
        duration_ms=12,
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
    )

    assert record.input_tokens == 10
    assert record.output_tokens == 5
    assert record.total_tokens == 15


def test_llm_call_record_stores_nullable_wire_api() -> None:
    default_record = LLMCallRecord(
        stage="analyst",
        provider="llm",
        model="relay-model",
        success=True,
        duration_ms=12,
    )
    responses_record = LLMCallRecord(
        stage="analyst",
        provider="llm",
        model="relay-model",
        wire_api="responses",
        success=True,
        duration_ms=12,
    )

    assert default_record.wire_api is None
    assert responses_record.wire_api == "responses"


def test_graph_state_starts_with_empty_llm_call_log() -> None:
    state = GraphState(user_request="Analyze AI coding agents")

    assert state.llm_call_log == []


def test_build_llm_call_record_sanitizes_secret_values() -> None:
    record = build_llm_call_record(
        stage="reporter",
        provider="llm",
        model="relay-model",
        success=False,
        duration_ms=3,
        error=RuntimeError("request failed for sk-secret-value"),
        secrets=["sk-secret-value"],
    )

    assert record.error == "RuntimeError: LLM call failed."
    assert "sk-secret-value" not in record.model_dump_json()


def test_build_llm_call_record_normalizes_negative_token_values() -> None:
    record = build_llm_call_record(
        stage="analyst",
        provider="llm",
        model="relay-model",
        success=True,
        duration_ms=12,
        input_tokens=-1,
        output_tokens=2,
        total_tokens=-3,
    )

    assert record.input_tokens is None
    assert record.output_tokens == 2
    assert record.total_tokens is None


def test_build_llm_call_record_stores_wire_api() -> None:
    record = build_llm_call_record(
        stage="analyst",
        provider="llm",
        model="relay-model",
        wire_api="responses",
        success=True,
        duration_ms=12,
    )

    assert record.wire_api == "responses"


def test_get_llm_wire_api_reads_optional_client_config() -> None:
    class ClientConfig:
        wire_api = "responses"

    class ConfiguredClient:
        config = ClientConfig()

    class LegacyClient:
        pass

    assert get_llm_wire_api(ConfiguredClient()) == "responses"
    assert get_llm_wire_api(LegacyClient()) is None


def test_complete_json_with_observability_uses_usage_aware_client() -> None:
    class UsageAwareClient:
        def complete_json_with_usage(self, messages: list[ChatMessage]) -> ChatCompletionResult:
            return ChatCompletionResult(
                content='{"ok": true}',
                input_tokens=3,
                output_tokens=4,
                total_tokens=7,
            )

        def complete_json(self, messages: list[ChatMessage]) -> str:
            raise AssertionError("complete_json should not be called")

    result = complete_json_with_observability(
        UsageAwareClient(), [ChatMessage(role="user", content="Return JSON")]
    )

    assert result == ChatCompletionResult(
        content='{"ok": true}',
        input_tokens=3,
        output_tokens=4,
        total_tokens=7,
    )


def test_complete_json_with_observability_falls_back_to_legacy_client() -> None:
    class LegacyClient:
        def complete_json(self, messages: list[ChatMessage]) -> str:
            return '{"ok": true}'

    result = complete_json_with_observability(
        LegacyClient(), [ChatMessage(role="user", content="Return JSON")]
    )

    assert result == ChatCompletionResult(content='{"ok": true}')


def test_llm_call_record_stores_router_metadata() -> None:
    record = LLMCallRecord(
        stage="analyst",
        provider="llm",
        model="fast-model",
        success=True,
        duration_ms=12,
        router="rules",
        router_tier="fast",
        router_reason="short_default_prompt",
        router_message_chars=123,
    )

    assert record.router == "rules"
    assert record.router_tier == "fast"
    assert record.router_reason == "short_default_prompt"
    assert record.router_message_chars == 123


def test_build_llm_call_record_copies_router_metadata() -> None:
    class RoutedClient:
        router_decision = LLMRouterDecision(
            router="rules",
            tier="strong",
            reason="long_prompt",
            message_chars=12001,
        )

    record = build_llm_call_record(
        stage="analyst",
        provider="llm",
        model="strong-model",
        success=True,
        duration_ms=12,
        llm_client=RoutedClient(),
    )

    assert record.router == "rules"
    assert record.router_tier == "strong"
    assert record.router_reason == "long_prompt"
    assert record.router_message_chars == 12001


def test_build_llm_call_record_omits_router_metadata_without_decision() -> None:
    class PlainClient:
        pass

    record = build_llm_call_record(
        stage="analyst",
        provider="llm",
        model="relay-model",
        success=True,
        duration_ms=12,
        llm_client=PlainClient(),
    )

    assert record.router is None
    assert record.router_tier is None
    assert record.router_reason is None
    assert record.router_message_chars is None


def test_router_metadata_does_not_store_prompt_content() -> None:
    class RoutedClient:
        router_decision = LLMRouterDecision(
            router="rules",
            tier="fast",
            reason="short_default_prompt",
            message_chars=19,
        )

    record = build_llm_call_record(
        stage="analyst",
        provider="llm",
        model="fast-model",
        success=True,
        duration_ms=12,
        llm_client=RoutedClient(),
    )

    serialized = record.model_dump_json()
    assert "Sensitive prompt" not in serialized
    assert record.router_message_chars == 19


def test_build_llm_call_record_does_not_store_raw_exception_payloads() -> None:
    record = build_llm_call_record(
        stage="reporter",
        provider="llm",
        model="relay-model",
        success=False,
        duration_ms=3,
        error=RuntimeError(
            "prompt=Sensitive prompt completion=Raw response authorization=Bearer token"
        ),
        secrets=["token"],
    )

    serialized = record.model_dump_json()
    assert record.error == "RuntimeError: LLM call failed."
    assert "Sensitive prompt" not in serialized
    assert "Raw response" not in serialized
    assert "Bearer" not in serialized
    assert "Bearer token" not in serialized
