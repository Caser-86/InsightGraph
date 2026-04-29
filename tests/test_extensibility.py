import json

from insight_graph.llm.trace_export import build_full_trace_event
from insight_graph.tools.code_execution import execute_code
from insight_graph.tools.mcp_registry import McpToolSpec, load_mcp_tool_specs


def test_build_full_trace_event_omits_messages_by_default() -> None:
    event = build_full_trace_event(
        stage="analyst",
        provider="openai_compatible",
        model="gpt-test",
        messages=[{"role": "user", "content": "secret prompt"}],
        output_text="secret output",
        token_usage={"total_tokens": 12},
    )

    assert event["stage"] == "analyst"
    assert event["provider"] == "openai_compatible"
    assert event["model"] == "gpt-test"
    assert event["token_usage"] == {"total_tokens": 12}
    assert "messages" not in event
    assert "output_text" not in event


def test_build_full_trace_event_includes_messages_when_explicitly_enabled() -> None:
    event = build_full_trace_event(
        stage="reporter",
        provider="openai_compatible",
        model="gpt-test",
        messages=[{"role": "user", "content": "prompt"}],
        output_text="output",
        token_usage={},
        include_payload=True,
    )

    assert event["messages"] == [{"role": "user", "content": "prompt"}]
    assert event["output_text"] == "output"


def test_load_mcp_tool_specs_reads_opt_in_json(monkeypatch) -> None:
    monkeypatch.setenv(
        "INSIGHT_GRAPH_MCP_TOOLS_JSON",
        json.dumps([{"name": "search", "description": "External search", "endpoint": "mcp://search"}]),
    )

    assert load_mcp_tool_specs() == [
        McpToolSpec(name="search", description="External search", endpoint="mcp://search")
    ]


def test_execute_code_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_ENABLE_CODE_EXECUTION", raising=False)

    result = execute_code("1 + 1")

    assert result.success is False
    assert result.error == "code execution disabled"


def test_execute_code_runs_restricted_expression_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ENABLE_CODE_EXECUTION", "1")

    result = execute_code("1 + 2 * 3")

    assert result.success is True
    assert result.output == "7"

    blocked = execute_code("__import__('os').system('echo unsafe')")
    assert blocked.success is False
    assert blocked.error == "unsupported expression"
