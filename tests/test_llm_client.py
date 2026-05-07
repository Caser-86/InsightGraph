import pytest

from insight_graph.llm import (
    ChatCompletionClient,
    ChatCompletionResult,
    ChatMessage,
    LLMConfig,
    OpenAICompatibleChatClient,
    get_llm_client,
    resolve_llm_config,
)
from insight_graph.llm.trace_writer import write_full_llm_trace_event


class FakeOpenAIMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class FakeOpenAIChoice:
    def __init__(self, message: FakeOpenAIMessage) -> None:
        self.message = message


class FakeOpenAIUsage:
    def __init__(
        self,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class FakeOpenAIResponse:
    def __init__(
        self,
        content: str | None,
        usage: FakeOpenAIUsage | None = None,
    ) -> None:
        self.choices = [FakeOpenAIChoice(FakeOpenAIMessage(content))]
        self.usage = usage


class FakeOpenAICompletions:
    def __init__(
        self,
        content: str | None = '{"ok": true}',
        error: Exception | None = None,
        usage: FakeOpenAIUsage | None = None,
    ) -> None:
        self.content = content
        self.error = error
        self.usage = usage
        self.calls: list[dict] = []
        self.errors: list[Exception] = []

    def create(self, **kwargs) -> FakeOpenAIResponse:
        self.calls.append(kwargs)
        if self.errors:
            raise self.errors.pop(0)
        if self.error is not None:
            raise self.error
        return FakeOpenAIResponse(self.content, usage=self.usage)


class FakeOpenAIChat:
    def __init__(self, completions: FakeOpenAICompletions) -> None:
        self.completions = completions


class FakeResponsesUsage:
    def __init__(
        self,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens


class FakeResponsesResponse:
    def __init__(
        self,
        output_text: str | None = '{"ok": true}',
        usage: FakeResponsesUsage | None = None,
    ) -> None:
        self.output_text = output_text
        self.output = []
        self.usage = usage


class FakeResponsesContent:
    def __init__(self, text: str | None) -> None:
        self.text = text


class FakeResponsesOutput:
    def __init__(self, content: list[FakeResponsesContent]) -> None:
        self.content = content


class FakeNestedResponsesResponse:
    def __init__(self, output: list[FakeResponsesOutput]) -> None:
        self.output_text = None
        self.output = output
        self.usage = None


class FakeOpenAIResponses:
    def __init__(
        self,
        output_text: str | None = '{"ok": true}',
        error: Exception | None = None,
        usage: FakeResponsesUsage | None = None,
        response: object | None = None,
    ) -> None:
        self.output_text = output_text
        self.error = error
        self.usage = usage
        self.response = response
        self.calls: list[dict] = []

    def create(self, **kwargs) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if self.response is not None:
            return self.response
        return FakeResponsesResponse(self.output_text, usage=self.usage)


class FakeOpenAIClient:
    def __init__(
        self,
        completions: FakeOpenAICompletions | None = None,
        responses: FakeOpenAIResponses | None = None,
    ) -> None:
        self.completions = completions or FakeOpenAICompletions()
        self.responses = responses or FakeOpenAIResponses()
        self.chat = FakeOpenAIChat(self.completions)


class FakeTraceClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config


def test_openai_compatible_chat_client_completes_json() -> None:
    completions = FakeOpenAICompletions(content='{"answer": "yes"}')
    fake_client = FakeOpenAIClient(completions)
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key="test-key", base_url=None, model="test-model"),
        client=fake_client,
    )

    result = client.complete_json([ChatMessage(role="user", content="Reply as JSON")])

    assert result == '{"answer": "yes"}'
    assert completions.calls == [
        {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Reply as JSON"}],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
    ]


def test_openai_compatible_chat_client_completes_json_with_usage() -> None:
    completions = FakeOpenAICompletions(
        content='{"answer": "yes"}',
        usage=FakeOpenAIUsage(prompt_tokens=11, completion_tokens=7, total_tokens=18),
    )
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key="test-key", base_url=None, model="test-model"),
        client=FakeOpenAIClient(completions),
    )

    result = client.complete_json_with_usage(
        [ChatMessage(role="user", content="Reply as JSON")]
    )

    assert result == ChatCompletionResult(
        content='{"answer": "yes"}',
        input_tokens=11,
        output_tokens=7,
        total_tokens=18,
    )


def test_openai_compatible_chat_client_passes_chat_output_token_limit() -> None:
    completions = FakeOpenAICompletions(content='{"answer": "yes"}')
    client = OpenAICompatibleChatClient(
        config=LLMConfig(
            api_key="test-key",
            base_url=None,
            model="test-model",
            max_output_tokens=32000,
        ),
        client=FakeOpenAIClient(completions),
    )

    client.complete_json([ChatMessage(role="user", content="Reply as JSON")])

    assert completions.calls[0]["max_tokens"] == 32000


def test_openai_compatible_chat_client_handles_missing_usage() -> None:
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key="test-key", base_url=None, model="test-model"),
        client=FakeOpenAIClient(FakeOpenAICompletions(content='{"answer": "yes"}')),
    )

    result = client.complete_json_with_usage(
        [ChatMessage(role="user", content="Reply as JSON")]
    )

    assert result == ChatCompletionResult(content='{"answer": "yes"}')


def test_openai_compatible_chat_client_complete_json_still_returns_content() -> None:
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key="test-key", base_url=None, model="test-model"),
        client=FakeOpenAIClient(
            FakeOpenAICompletions(
                content='{"answer": "yes"}',
                usage=FakeOpenAIUsage(prompt_tokens=11, completion_tokens=7, total_tokens=18),
            )
        ),
    )

    assert client.complete_json([ChatMessage(role="user", content="Reply as JSON")]) == (
        '{"answer": "yes"}'
    )


def test_openai_compatible_chat_client_uses_responses_wire_api() -> None:
    responses = FakeOpenAIResponses(output_text='{"answer": "yes"}')
    client = OpenAICompatibleChatClient(
        config=LLMConfig(
            api_key="test-key",
            base_url=None,
            model="test-model",
            wire_api="responses",
        ),
        client=FakeOpenAIClient(responses=responses),
    )

    result = client.complete_json([ChatMessage(role="user", content="Reply as JSON")])

    assert result == '{"answer": "yes"}'
    assert responses.calls == [
        {
            "model": "test-model",
            "input": [{"role": "user", "content": "Reply as JSON"}],
            "text": {"format": {"type": "json_object"}},
            "temperature": 0,
        }
    ]


def test_openai_compatible_chat_client_maps_responses_usage() -> None:
    responses = FakeOpenAIResponses(
        output_text='{"answer": "yes"}',
        usage=FakeResponsesUsage(input_tokens=13, output_tokens=5, total_tokens=18),
    )
    client = OpenAICompatibleChatClient(
        config=LLMConfig(
            api_key="test-key",
            base_url=None,
            model="test-model",
            wire_api="responses",
        ),
        client=FakeOpenAIClient(responses=responses),
    )

    result = client.complete_json_with_usage(
        [ChatMessage(role="user", content="Reply as JSON")]
    )

    assert result == ChatCompletionResult(
        content='{"answer": "yes"}',
        input_tokens=13,
        output_tokens=5,
        total_tokens=18,
    )


def test_openai_compatible_chat_client_passes_responses_output_token_limit() -> None:
    responses = FakeOpenAIResponses(output_text='{"answer": "yes"}')
    client = OpenAICompatibleChatClient(
        config=LLMConfig(
            api_key="test-key",
            base_url=None,
            model="test-model",
            wire_api="responses",
            max_output_tokens=64000,
        ),
        client=FakeOpenAIClient(responses=responses),
    )

    client.complete_json([ChatMessage(role="user", content="Reply as JSON")])

    assert responses.calls[0]["max_output_tokens"] == 64000


def test_openai_compatible_chat_client_reads_nested_responses_output_text() -> None:
    responses = FakeOpenAIResponses(
        response=FakeNestedResponsesResponse(
            [FakeResponsesOutput([FakeResponsesContent('{"answer": "nested"}')])]
        )
    )
    client = OpenAICompatibleChatClient(
        config=LLMConfig(
            api_key="test-key",
            base_url=None,
            model="test-model",
            wire_api="responses",
        ),
        client=FakeOpenAIClient(responses=responses),
    )

    result = client.complete_json([ChatMessage(role="user", content="Reply as JSON")])

    assert result == '{"answer": "nested"}'


def test_openai_compatible_chat_client_requires_responses_content() -> None:
    responses = FakeOpenAIResponses(
        response=FakeNestedResponsesResponse([FakeResponsesOutput([FakeResponsesContent(None)])])
    )
    client = OpenAICompatibleChatClient(
        config=LLMConfig(
            api_key="test-key",
            base_url=None,
            model="test-model",
            wire_api="responses",
        ),
        client=FakeOpenAIClient(responses=responses),
    )

    with pytest.raises(ValueError, match="response content"):
        client.complete_json([ChatMessage(role="user", content="Reply as JSON")])


def test_openai_compatible_chat_client_uses_factory_with_base_url() -> None:
    created: list[dict] = []

    def client_factory(**kwargs) -> FakeOpenAIClient:
        created.append(kwargs)
        return FakeOpenAIClient()

    client = OpenAICompatibleChatClient(
        config=LLMConfig(
            api_key="test-key",
            base_url="https://openai-compatible.example/v1",
            model="test-model",
        ),
        client_factory=client_factory,
    )

    result = client.complete_json([ChatMessage(role="system", content="Return JSON")])

    assert result == '{"ok": true}'
    assert created == [
        {
            "api_key": "test-key",
            "base_url": "https://openai-compatible.example/v1",
        }
    ]


def test_openai_compatible_chat_client_requires_api_key() -> None:
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key=None, base_url=None, model="test-model"),
        client=FakeOpenAIClient(),
    )

    with pytest.raises(ValueError, match="api_key"):
        client.complete_json([ChatMessage(role="user", content="Return JSON")])


def test_resolve_llm_config_reads_max_output_tokens(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MAX_OUTPUT_TOKENS", "48000")

    config = resolve_llm_config(api_key="test-key", model="test-model")

    assert config.max_output_tokens == 48000


def test_resolve_llm_config_reads_retry_and_fallback(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MAX_RETRIES", "3")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_RETRY_BACKOFF_SECONDS", "0.25")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_FALLBACK_MODELS", "deepseek-chat,qwen-max")

    config = resolve_llm_config(api_key="test-key", model="deepseek-reasoner")

    assert config.max_retries == 3
    assert config.retry_backoff_seconds == 0.25
    assert config.fallback_models == ("deepseek-chat", "qwen-max")


def test_openai_compatible_chat_client_retries_then_succeeds(monkeypatch) -> None:
    monkeypatch.setattr("insight_graph.llm.client.time.sleep", lambda _: None)
    completions = FakeOpenAICompletions(content='{"answer": "yes"}')
    completions.errors = [RuntimeError("transient"), RuntimeError("transient")]
    client = OpenAICompatibleChatClient(
        config=LLMConfig(
            api_key="test-key",
            base_url=None,
            model="test-model",
            max_retries=2,
            retry_backoff_seconds=0.01,
        ),
        client=FakeOpenAIClient(completions),
    )

    result = client.complete_json([ChatMessage(role="user", content="Return JSON")])

    assert result == '{"answer": "yes"}'
    assert len(completions.calls) == 3


def test_openai_compatible_chat_client_falls_back_model_after_primary_failures(
    monkeypatch,
) -> None:
    monkeypatch.setattr("insight_graph.llm.client.time.sleep", lambda _: None)
    completions = FakeOpenAICompletions(content='{"answer": "fallback"}')
    completions.errors = [RuntimeError("primary down")]
    client = OpenAICompatibleChatClient(
        config=LLMConfig(
            api_key="test-key",
            base_url=None,
            model="primary-model",
            max_retries=0,
            fallback_models=("fallback-model",),
        ),
        client=FakeOpenAIClient(completions),
    )

    result = client.complete_json([ChatMessage(role="user", content="Return JSON")])

    assert result == '{"answer": "fallback"}'
    assert [call["model"] for call in completions.calls] == [
        "primary-model",
        "fallback-model",
    ]


def test_openai_compatible_chat_client_propagates_api_error() -> None:
    api_error = RuntimeError("upstream failed")
    client = OpenAICompatibleChatClient(
        config=LLMConfig(
            api_key="test-key",
            base_url=None,
            model="test-model",
            max_retries=0,
        ),
        client=FakeOpenAIClient(FakeOpenAICompletions(error=api_error)),
    )

    with pytest.raises(RuntimeError, match="upstream failed"):
        client.complete_json([ChatMessage(role="user", content="Return JSON")])


def test_get_llm_client_returns_openai_compatible_client() -> None:
    client = get_llm_client(config=LLMConfig(api_key="test-key", base_url=None, model="test-model"))

    assert isinstance(client, OpenAICompatibleChatClient)


def test_full_llm_trace_redacts_secrets_and_omits_payload_by_default(
    monkeypatch,
    tmp_path,
) -> None:
    trace_path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_TRACE_PATH", str(trace_path))
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_TRACE_FULL", raising=False)
    client = FakeTraceClient(
        LLMConfig(api_key="sk-secret", base_url=None, model="test-model")
    )

    write_full_llm_trace_event(
        stage="analyst",
        llm_client=client,
        messages=[ChatMessage(role="user", content="API key sk-secret prompt")],
        output_text="completion with sk-secret",
        duration_ms=12,
        success=True,
        input_tokens=1,
        output_tokens=2,
        total_tokens=3,
    )

    content = trace_path.read_text(encoding="utf-8")
    assert "sk-secret" not in content
    assert "API key" not in content
    assert "completion with" not in content
    assert "token_usage" in content


def test_full_llm_trace_payload_is_explicit_opt_in_and_redacted(
    monkeypatch,
    tmp_path,
) -> None:
    trace_path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_TRACE_PATH", str(trace_path))
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_TRACE_FULL", "1")
    client = FakeTraceClient(
        LLMConfig(api_key="sk-secret", base_url=None, model="test-model")
    )

    write_full_llm_trace_event(
        stage="analyst",
        llm_client=client,
        messages=[ChatMessage(role="user", content="API key sk-secret prompt")],
        output_text="completion with sk-secret",
        duration_ms=12,
        success=True,
    )

    content = trace_path.read_text(encoding="utf-8")
    assert "sk-secret" not in content
    assert "[REDACTED]" in content
    assert "API key [REDACTED] prompt" in content
    assert "completion with [REDACTED]" in content


def test_llm_package_exports_core_types() -> None:
    assert ChatCompletionClient is not None
    assert ChatCompletionResult(content="{}").content == "{}"
    assert ChatMessage(role="user", content="Hello").content == "Hello"
    assert LLMConfig(api_key="key", base_url=None, model="model").model == "model"
    assert OpenAICompatibleChatClient is not None
    assert get_llm_client is not None
    assert resolve_llm_config is not None
