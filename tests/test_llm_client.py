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

    def create(self, **kwargs) -> FakeOpenAIResponse:
        self.calls.append(kwargs)
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


class FakeOpenAIResponses:
    def __init__(
        self,
        output_text: str | None = '{"ok": true}',
        error: Exception | None = None,
        usage: FakeResponsesUsage | None = None,
    ) -> None:
        self.output_text = output_text
        self.error = error
        self.usage = usage
        self.calls: list[dict] = []

    def create(self, **kwargs) -> FakeResponsesResponse:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
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


def test_openai_compatible_chat_client_propagates_api_error() -> None:
    api_error = RuntimeError("upstream failed")
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key="test-key", base_url=None, model="test-model"),
        client=FakeOpenAIClient(FakeOpenAICompletions(error=api_error)),
    )

    with pytest.raises(RuntimeError, match="upstream failed"):
        client.complete_json([ChatMessage(role="user", content="Return JSON")])


def test_get_llm_client_returns_openai_compatible_client() -> None:
    client = get_llm_client(config=LLMConfig(api_key="test-key", base_url=None, model="test-model"))

    assert isinstance(client, OpenAICompatibleChatClient)


def test_llm_package_exports_core_types() -> None:
    assert ChatCompletionClient is not None
    assert ChatCompletionResult(content="{}").content == "{}"
    assert ChatMessage(role="user", content="Hello").content == "Hello"
    assert LLMConfig(api_key="key", base_url=None, model="model").model == "model"
    assert OpenAICompatibleChatClient is not None
    assert get_llm_client is not None
    assert resolve_llm_config is not None
