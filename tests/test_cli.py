import json
import os

from typer.testing import CliRunner

import insight_graph.cli as cli_module
from insight_graph.cli import app
from insight_graph.state import (
    CompetitiveMatrixRow,
    Critique,
    Evidence,
    Finding,
    GraphState,
    LLMCallRecord,
    Subtask,
    ToolCallRecord,
)


def clear_llm_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_PROVIDER",
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_LLM_BASE_URL",
        "INSIGHT_GRAPH_LLM_MODEL",
        "INSIGHT_GRAPH_USE_WEB_SEARCH",
        "INSIGHT_GRAPH_SEARCH_PROVIDER",
        "INSIGHT_GRAPH_SEARCH_LIMIT",
        "INSIGHT_GRAPH_USE_GITHUB_SEARCH",
        "INSIGHT_GRAPH_GITHUB_PROVIDER",
        "INSIGHT_GRAPH_USE_SEC_FILINGS",
        "INSIGHT_GRAPH_USE_SEC_FINANCIALS",
        "INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION",
        "INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS",
        "INSIGHT_GRAPH_MAX_TOOL_CALLS",
        "INSIGHT_GRAPH_MAX_FETCHES",
        "INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN",
        "INSIGHT_GRAPH_MAX_TOKENS",
        "INSIGHT_GRAPH_LLM_MAX_OUTPUT_TOKENS",
        "INSIGHT_GRAPH_REPORT_INTENSITY",
        "INSIGHT_GRAPH_REPORT_REVIEW_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_VALIDATE_URLS",
        "INSIGHT_GRAPH_RELEVANCE_FILTER",
        "INSIGHT_GRAPH_RELEVANCE_JUDGE",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


def test_cli_research_outputs_markdown_report(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents"])

    assert result.exit_code == 0
    assert "# InsightGraph 深度研究报告" in result.output
    assert "## References" in result.output


def test_configure_output_encoding_uses_utf8_when_supported() -> None:
    class FakeStream:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []

        def reconfigure(self, **kwargs: str) -> None:
            self.calls.append(kwargs)

    stdout = FakeStream()
    stderr = FakeStream()

    cli_module._configure_output_encoding(stdout=stdout, stderr=stderr)

    assert stdout.calls == [{"encoding": "utf-8"}]
    assert stderr.calls == [{"encoding": "utf-8"}]


def test_configure_output_encoding_ignores_unsupported_streams() -> None:
    class UnsupportedStream:
        def reconfigure(self, **kwargs: str) -> None:
            raise ValueError("unsupported")

    cli_module._configure_output_encoding(
        stdout=UnsupportedStream(), stderr=UnsupportedStream()
    )


def test_apply_live_llm_preset_sets_missing_runtime_defaults(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    cli_module._apply_research_preset(cli_module.ResearchPreset.live_llm)

    assert os.environ["INSIGHT_GRAPH_USE_WEB_SEARCH"] == "1"
    assert os.environ["INSIGHT_GRAPH_SEARCH_PROVIDER"] == "duckduckgo"
    assert os.environ["INSIGHT_GRAPH_RELEVANCE_FILTER"] == "1"
    assert os.environ["INSIGHT_GRAPH_RELEVANCE_JUDGE"] == "openai_compatible"
    assert os.environ["INSIGHT_GRAPH_ANALYST_PROVIDER"] == "llm"
    assert os.environ["INSIGHT_GRAPH_REPORTER_PROVIDER"] == "llm"


def test_apply_live_research_preset_sets_network_defaults(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    cli_module._apply_research_preset(cli_module.ResearchPreset.live_research)

    assert os.environ["INSIGHT_GRAPH_USE_WEB_SEARCH"] == "1"
    assert os.environ["INSIGHT_GRAPH_SEARCH_PROVIDER"] == "duckduckgo"
    assert os.environ["INSIGHT_GRAPH_SEARCH_LIMIT"] == "20"
    assert os.environ["INSIGHT_GRAPH_USE_GITHUB_SEARCH"] == "1"
    assert os.environ["INSIGHT_GRAPH_GITHUB_PROVIDER"] == "live"
    assert os.environ["INSIGHT_GRAPH_USE_SEC_FILINGS"] == "1"
    assert os.environ["INSIGHT_GRAPH_USE_SEC_FINANCIALS"] == "1"
    assert os.environ["INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION"] == "1"
    assert os.environ["INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS"] == "5"
    assert os.environ["INSIGHT_GRAPH_MAX_TOOL_CALLS"] == "200"
    assert os.environ["INSIGHT_GRAPH_MAX_FETCHES"] == "80"
    assert os.environ["INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN"] == "120"
    assert os.environ["INSIGHT_GRAPH_REPORTER_VALIDATE_URLS"] == "1"
    assert os.environ["INSIGHT_GRAPH_RELEVANCE_FILTER"] == "1"
    assert os.environ["INSIGHT_GRAPH_RELEVANCE_JUDGE"] == "openai_compatible"
    assert os.environ["INSIGHT_GRAPH_ANALYST_PROVIDER"] == "llm"
    assert os.environ["INSIGHT_GRAPH_REPORTER_PROVIDER"] == "llm"


def test_apply_live_llm_preset_preserves_explicit_env_values(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "deterministic")

    cli_module._apply_research_preset(cli_module.ResearchPreset.live_llm)

    assert os.environ["INSIGHT_GRAPH_SEARCH_PROVIDER"] == "mock"
    assert os.environ["INSIGHT_GRAPH_REPORTER_PROVIDER"] == "deterministic"
    assert os.environ["INSIGHT_GRAPH_USE_WEB_SEARCH"] == "1"
    assert os.environ["INSIGHT_GRAPH_ANALYST_PROVIDER"] == "llm"


def test_apply_offline_preset_does_not_set_live_defaults(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    cli_module._apply_research_preset(cli_module.ResearchPreset.offline)

    assert "INSIGHT_GRAPH_USE_WEB_SEARCH" not in os.environ


def test_cli_report_intensity_overrides_runtime_budget(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    observed = {}

    def fake_run_research(query: str) -> GraphState:
        observed["query"] = query
        observed["intensity"] = os.environ["INSIGHT_GRAPH_REPORT_INTENSITY"]
        observed["tokens"] = os.environ["INSIGHT_GRAPH_MAX_TOKENS"]
        observed["output_tokens"] = os.environ["INSIGHT_GRAPH_LLM_MAX_OUTPUT_TOKENS"]
        observed["tool_calls"] = os.environ["INSIGHT_GRAPH_MAX_TOOL_CALLS"]
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)

    result = CliRunner().invoke(
        app,
        [
            "research",
            "Compare AI coding agents",
            "--report-intensity",
            "deep",
            "--output-json",
        ],
    )

    assert result.exit_code == 0
    assert observed == {
        "query": "Compare AI coding agents",
        "intensity": "deep",
        "tokens": "2000000",
        "output_tokens": "64000",
        "tool_calls": "700",
    }
    payload = json.loads(result.output)
    assert payload["runtime_diagnostics"]["report_intensity"] == "deep"
    assert payload["runtime_diagnostics"]["search_provider_expression"] == "mock"
    assert payload["runtime_diagnostics"]["resolved_search_providers"] == ["mock"]
    assert payload["runtime_diagnostics"]["serpapi_enabled"] is False
    assert payload["runtime_diagnostics"]["research_jobs_backend"] == "memory"
    assert payload["runtime_diagnostics"]["research_jobs_json_path"] is None
    assert payload["runtime_diagnostics"]["research_jobs_sqlite_path"] is None
    assert payload["runtime_diagnostics"]["event_retention_limit"] is None
    assert "INSIGHT_GRAPH_SEARCH_PROVIDER" not in os.environ
    assert "INSIGHT_GRAPH_RELEVANCE_FILTER" not in os.environ
    assert "INSIGHT_GRAPH_RELEVANCE_JUDGE" not in os.environ
    assert "INSIGHT_GRAPH_ANALYST_PROVIDER" not in os.environ
    assert "INSIGHT_GRAPH_REPORTER_PROVIDER" not in os.environ


def test_cli_live_llm_preset_applies_defaults_before_workflow(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in cli_module.LIVE_LLM_PRESET_DEFAULTS}
        )
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--preset", "live-llm"]
    )

    assert result.exit_code == 0
    assert observed_env == cli_module.LIVE_LLM_PRESET_DEFAULTS
    assert "# Report" in result.output


def test_cli_live_research_preset_applies_defaults_before_workflow(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in cli_module.LIVE_RESEARCH_PRESET_DEFAULTS}
        )
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--preset", "live-research"]
    )

    assert result.exit_code == 0
    assert observed_env == cli_module.LIVE_RESEARCH_PRESET_DEFAULTS
    assert "# Report" in result.output


def test_cli_offline_preset_does_not_apply_live_defaults(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in cli_module.LIVE_LLM_PRESET_DEFAULTS}
        )
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--preset", "offline"]
    )

    assert result.exit_code == 0
    assert observed_env == {name: None for name in cli_module.LIVE_LLM_PRESET_DEFAULTS}


def test_cli_rejects_unknown_preset_before_workflow(monkeypatch) -> None:
    def fail_if_called(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    monkeypatch.setattr(cli_module, "run_research", fail_if_called)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents", "--preset", "bad"])

    assert result.exit_code != 0
    assert "bad" in result.output


def test_cli_research_does_not_show_llm_log_by_default(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay-model",
                success=True,
                duration_ms=12,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents"])

    assert result.exit_code == 0
    assert "# Report" in result.output
    assert "## LLM Call Log" not in result.output
    assert "relay-model" not in result.output


def test_cli_research_show_llm_log_appends_metadata_table(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.extend(
            [
                LLMCallRecord(
                    stage="relevance",
                    provider="openai_compatible",
                    model="relay-model",
                    wire_api="responses",
                    success=True,
                    duration_ms=7,
                ),
                LLMCallRecord(
                    stage="reporter",
                    provider="llm",
                    model="relay-model",
                    success=False,
                    duration_ms=9,
                    error="ReporterFallbackError: LLM call failed.",
                ),
            ]
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "# Report" in result.output
    assert "## LLM Call Log" in result.output
    assert (
        "| Stage | Provider | Model | Router | Tier | Reason | Wire API | Success | Duration ms | "
        "Input tokens | Output tokens | Total tokens | Error |"
    ) in result.output
    assert (
        "| relevance | openai_compatible | relay-model | - | - | - | responses | "
        "true | 7 |  |  |  |  |"
        in result.output
    )
    assert (
        "| reporter | llm | relay-model | - | - | - |  | false | 9 |  |  |  | "
        "ReporterFallbackError: LLM call failed. |"
    ) in result.output


def test_cli_research_show_llm_log_includes_token_columns(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay-model",
                success=True,
                duration_ms=12,
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    result = CliRunner().invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert (
        "| analyst | llm | relay-model | - | - | - |  | true | 12 | 10 | 5 | 15 |  |"
        in result.output
    )


def test_cli_research_show_llm_log_includes_router_columns(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="fast-model",
                success=True,
                duration_ms=12,
                router="rules",
                router_tier="fast",
                router_reason="short_default_prompt",
                router_message_chars=19,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)

    result = CliRunner().invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "| Stage | Provider | Model | Router | Tier | Reason | Wire API |" in result.output
    assert "| analyst | llm | fast-model | rules | fast | short_default_prompt |" in result.output


def test_cli_research_show_llm_log_renders_missing_router_metadata_as_dash(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="reporter",
                provider="llm",
                model="relay-model",
                success=True,
                duration_ms=12,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)

    result = CliRunner().invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "| reporter | llm | relay-model | - | - | - |" in result.output


def test_cli_research_output_json_includes_router_metadata(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="fast-model",
                success=True,
                duration_ms=12,
                router="rules",
                router_tier="fast",
                router_reason="short_default_prompt",
                router_message_chars=19,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)

    result = CliRunner().invoke(
        app, ["research", "Compare AI coding agents", "--output-json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["llm_call_log"][0]["router"] == "rules"
    assert payload["llm_call_log"][0]["router_tier"] == "fast"
    assert payload["llm_call_log"][0]["router_reason"] == "short_default_prompt"
    assert payload["llm_call_log"][0]["router_message_chars"] == 19


def test_cli_research_show_llm_log_reports_empty_log(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "# Report" in result.output
    assert "## LLM Call Log" in result.output
    assert "| Model | Router | Tier | Reason | Wire API | Success |" in result.output
    assert "| Input tokens | Output tokens | Total tokens |" in result.output
    assert "No LLM calls were recorded." in result.output


def test_cli_research_show_llm_log_escapes_cells_and_omits_raw_payloads(
    monkeypatch,
) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay|model\nsecond-line",
                success=False,
                duration_ms=3,
                error="RuntimeError: LLM call failed.",
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "relay\\|model second-line" in result.output
    assert "RuntimeError: LLM call failed." in result.output
    assert "Sensitive prompt" not in result.output
    assert "Raw response" not in result.output
    assert "sk-secret" not in result.output
    assert "Authorization" not in result.output


def test_cli_research_output_json_emits_parseable_summary(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(
            user_request=query,
            report_markdown="# Report\n",
            findings=[
                Finding(
                    title="Pricing differs",
                    summary="Pricing and packaging differ.",
                    evidence_ids=["cursor-pricing"],
                )
            ],
            critique=Critique(passed=True, reason="Enough evidence."),
            iterations=1,
        )
        state.tool_call_log.append(
            ToolCallRecord(
                subtask_id="collect",
                tool_name="mock_search",
                query=query,
                evidence_count=2,
            )
        )
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay-model",
                wire_api="responses",
                success=True,
                duration_ms=12,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--output-json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    trace_id = payload.pop("trace_id")
    assert trace_id
    assert payload["user_request"] == "Compare AI coding agents"
    assert payload["report_markdown"] == "# Report\n"
    assert payload["findings"] == [
        {
            "title": "Pricing differs",
            "summary": "Pricing and packaging differ.",
            "evidence_ids": ["cursor-pricing"],
        }
    ]
    assert payload["competitive_matrix"] == []
    assert payload["critique"] == {
        "passed": True,
        "reason": "Enough evidence.",
        "missing_topics": [],
    }
    assert payload["tool_call_log"] == [
        {
            "subtask_id": "collect",
            "tool_name": "mock_search",
            "query": "Compare AI coding agents",
            "evidence_count": 2,
            "filtered_count": 0,
            "success": True,
            "error": None,
            "round_index": 1,
            "section_id": None,
            "strategy_id": None,
            "stop_reason": None,
        }
    ]
    assert payload["llm_call_log"] == [
        {
            "stage": "analyst",
            "provider": "llm",
            "model": "relay-model",
            "wire_api": "responses",
            "success": True,
            "duration_ms": 12,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "router": None,
            "router_tier": None,
            "router_reason": None,
            "router_message_chars": None,
            "error": None,
        }
    ]
    assert payload["iterations"] == 1
    assert payload["evidence_pool"] == []
    assert payload["global_evidence_pool"] == []
    assert payload["citation_support"] == []
    assert payload["url_validation"] == []
    assert "quality" in payload
    assert "quality_cards" in payload
    assert "runtime_diagnostics" in payload


def test_cli_json_payload_includes_competitive_matrix(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return GraphState(
            user_request=query,
            competitive_matrix=[
                CompetitiveMatrixRow(
                    product="Cursor",
                    positioning="Official product positioning signal",
                    strengths=["Official/documented source coverage"],
                    evidence_ids=["cursor-pricing"],
                )
            ],
            report_markdown="# Report\n",
        )

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents", "--output-json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["competitive_matrix"] == [
        {
            "product": "Cursor",
            "positioning": "Official product positioning signal",
            "strengths": ["Official/documented source coverage"],
            "evidence_ids": ["cursor-pricing"],
        }
    ]


def test_cli_research_output_json_includes_tool_failure_records(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.tool_call_log.extend(
            [
                ToolCallRecord(
                    subtask_id="collect",
                    tool_name="web_search",
                    query=query,
                    success=False,
                    error="web_search returned no live evidence",
                ),
            ]
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    result = CliRunner().invoke(
        app, ["research", "Compare AI coding agents", "--output-json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [record["tool_name"] for record in payload["tool_call_log"]] == ["web_search"]
    assert payload["tool_call_log"][0]["success"] is False
    assert payload["tool_call_log"][0]["error"] == "web_search returned no live evidence"


def test_cli_research_default_output_is_not_json(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents"])

    assert result.exit_code == 0
    assert result.output.startswith("# Report")
    try:
        json.loads(result.output)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("Default research output should remain Markdown")


def test_cli_research_output_json_redacts_evidence_private_strings(
    monkeypatch,
) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(
            user_request=query,
            report_markdown="# Report\n",
            subtasks=[Subtask(id="secret-subtask", description="Sensitive prompt")],
            evidence_pool=[
                Evidence(
                    id="secret-evidence",
                    subtask_id="collect",
                    title="Raw response",
                    source_url="https://example.com/private",
                    snippet="sk-secret Authorization request-body Sensitive prompt",
                    verified=True,
                )
            ],
            global_evidence_pool=[
                Evidence(
                    id="global-secret-evidence",
                    subtask_id="collect",
                    title="Header",
                    source_url="https://example.com/global-private",
                    snippet="Raw response should not be exported",
                    verified=True,
                )
            ],
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--output-json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "subtasks" not in payload
    assert payload["evidence_pool"][0]["id"] == "secret-evidence"
    assert payload["global_evidence_pool"][0]["id"] == "global-secret-evidence"
    serialized = json.dumps(payload)
    assert "secret-subtask" not in serialized
    assert "Sensitive prompt" not in serialized
    assert "sk-secret" not in serialized
    assert "Authorization" not in serialized
    assert "request-body" not in serialized


def test_cli_research_output_json_takes_precedence_over_show_llm_log(
    monkeypatch,
) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="reporter",
                provider="llm",
                model="relay-model",
                success=True,
                duration_ms=4,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "research",
            "Compare AI coding agents",
            "--output-json",
            "--show-llm-log",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["llm_call_log"][0]["stage"] == "reporter"
    assert "## LLM Call Log" not in result.output
    assert "| Stage | Provider | Model |" not in result.output
