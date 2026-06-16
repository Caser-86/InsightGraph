import json
from pathlib import Path

from insight_graph.llm.trace_export import build_full_trace_event
from insight_graph.llm.trace_writer import (
    is_llm_trace_enabled,
    resolve_llm_trace_path,
    write_llm_trace_event,
)
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


def test_llm_trace_writer_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_TRACE", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_TRACE_PATH", raising=False)

    assert is_llm_trace_enabled() is False


def test_llm_trace_writer_uses_default_log_path(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_TRACE", "1")
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_TRACE_PATH", raising=False)

    assert resolve_llm_trace_path() == Path("llm_logs/llm-trace.jsonl")


def test_llm_trace_writer_appends_jsonl(tmp_path, monkeypatch) -> None:
    trace_path = tmp_path / "nested" / "trace.jsonl"
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_TRACE_PATH", str(trace_path))

    write_llm_trace_event({"stage": "reporter", "token_usage": {"total_tokens": 3}})
    write_llm_trace_event({"stage": "analyst", "token_usage": {"total_tokens": 5}})

    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["stage"] for line in lines] == ["reporter", "analyst"]


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
