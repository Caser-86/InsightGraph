# OpenAI Responses Wire API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit `responses` wire API support to the existing OpenAI-compatible LLM client while keeping Chat Completions as the default.

**Architecture:** Extend `LLMConfig` with a validated `wire_api` setting. Keep `OpenAICompatibleChatClient` as the stable public client and branch internally between `client.chat.completions.create(...)` and `client.responses.create(...)`, returning the existing `ChatCompletionResult` shape for both paths.

**Tech Stack:** Python 3.13, Pydantic, OpenAI Python SDK-compatible fake clients, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/llm/config.py`: add supported wire API constants, `LLMConfig.wire_api`, validation, and env resolution for `INSIGHT_GRAPH_LLM_WIRE_API`.
- Modify `src/insight_graph/llm/client.py`: keep the public client interface, split Chat Completions and Responses request paths, extract Responses text, and map Responses usage.
- Modify `tests/test_llm_config.py`: cover default wire API, env resolution, explicit override, and invalid value handling.
- Modify `tests/test_llm_client.py`: extend fake OpenAI client with `.responses.create(...)` and cover Responses request, content extraction, usage, and `complete_json()` compatibility.

---

### Task 1: Add Validated Wire API Configuration

**Files:**
- Modify: `src/insight_graph/llm/config.py`
- Modify: `tests/test_llm_config.py`

- [ ] **Step 1: Write failing config tests**

Add these tests to `tests/test_llm_config.py` after `test_resolve_llm_config_falls_back_to_openai_env()`:

```python
import pytest


def test_resolve_llm_config_defaults_to_chat_completions(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_WIRE_API", raising=False)

    config = resolve_llm_config()

    assert config.wire_api == "chat_completions"


def test_resolve_llm_config_reads_wire_api_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_WIRE_API", "responses")

    config = resolve_llm_config()

    assert config.wire_api == "responses"


def test_resolve_llm_config_explicit_wire_api_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_WIRE_API", "responses")

    config = resolve_llm_config(wire_api="chat_completions")

    assert config.wire_api == "chat_completions"


def test_resolve_llm_config_rejects_unknown_wire_api(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_WIRE_API", "not-real")

    with pytest.raises(ValueError, match="wire_api"):
        resolve_llm_config()
```

Also update the existing import at the top of `tests/test_llm_config.py` from:

```python
from insight_graph.llm.config import resolve_llm_config
```

to:

```python
import pytest

from insight_graph.llm.config import resolve_llm_config
```

Do not leave a duplicate `import pytest` near the added tests.

- [ ] **Step 2: Run config tests and verify RED**

Run:

```powershell
python -m pytest tests/test_llm_config.py -q
```

Expected: FAIL because `LLMConfig` does not yet expose `wire_api`, and `resolve_llm_config()` does not accept `wire_api`.

- [ ] **Step 3: Implement wire API config**

Replace `src/insight_graph/llm/config.py` with:

```python
from __future__ import annotations

import os

from pydantic import BaseModel, field_validator


DEFAULT_LLM_WIRE_API = "chat_completions"
SUPPORTED_LLM_WIRE_APIS = frozenset({"chat_completions", "responses"})


class LLMConfig(BaseModel):
    api_key: str | None
    base_url: str | None
    model: str
    wire_api: str = DEFAULT_LLM_WIRE_API

    @field_validator("wire_api")
    @classmethod
    def validate_wire_api(cls, value: str) -> str:
        if value not in SUPPORTED_LLM_WIRE_APIS:
            supported = ", ".join(sorted(SUPPORTED_LLM_WIRE_APIS))
            raise ValueError(
                f"Unsupported wire_api: {value}. Supported values: {supported}"
            )
        return value


def resolve_llm_config(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    wire_api: str | None = None,
) -> LLMConfig:
    return LLMConfig(
        api_key=api_key
        if api_key is not None
        else os.getenv("INSIGHT_GRAPH_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=base_url
        if base_url is not None
        else os.getenv("INSIGHT_GRAPH_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
        model=model
        if model is not None
        else os.getenv("INSIGHT_GRAPH_LLM_MODEL") or "gpt-4o-mini",
        wire_api=wire_api
        if wire_api is not None
        else os.getenv("INSIGHT_GRAPH_LLM_WIRE_API") or DEFAULT_LLM_WIRE_API,
    )
```

- [ ] **Step 4: Run config tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_llm_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add src/insight_graph/llm/config.py tests/test_llm_config.py
git commit -m "feat: configure llm wire api"
```

---

### Task 2: Add Responses API Request Path And Output Text Parsing

**Files:**
- Modify: `src/insight_graph/llm/client.py`
- Modify: `tests/test_llm_client.py`

- [ ] **Step 1: Extend fake client test helpers**

In `tests/test_llm_client.py`, add these helper classes after `FakeOpenAIChat` and before `FakeOpenAIClient`:

```python
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
```

Update `FakeOpenAIClient` from:

```python
class FakeOpenAIClient:
    def __init__(self, completions: FakeOpenAICompletions | None = None) -> None:
        self.completions = completions or FakeOpenAICompletions()
        self.chat = FakeOpenAIChat(self.completions)
```

to:

```python
class FakeOpenAIClient:
    def __init__(
        self,
        completions: FakeOpenAICompletions | None = None,
        responses: FakeOpenAIResponses | None = None,
    ) -> None:
        self.completions = completions or FakeOpenAICompletions()
        self.responses = responses or FakeOpenAIResponses()
        self.chat = FakeOpenAIChat(self.completions)
```

- [ ] **Step 2: Write failing Responses request and output_text tests**

Add these tests after `test_openai_compatible_chat_client_complete_json_still_returns_content()`:

```python
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
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_llm_client.py::test_openai_compatible_chat_client_uses_responses_wire_api tests/test_llm_client.py::test_openai_compatible_chat_client_maps_responses_usage -q
```

Expected: FAIL because `complete_json_with_usage()` still always calls `chat.completions.create(...)`.

- [ ] **Step 4: Implement Responses request path**

In `src/insight_graph/llm/client.py`, replace `complete_json_with_usage()` with:

```python
    def complete_json_with_usage(
        self,
        messages: list[ChatMessage],
    ) -> ChatCompletionResult:
        if not self.config.api_key:
            raise ValueError("LLM api_key is required")

        if self.config.wire_api == "responses":
            return self._complete_json_with_responses(messages)
        return self._complete_json_with_chat_completions(messages)
```

Add these methods inside `OpenAICompatibleChatClient` below `complete_json_with_usage()` and above `_get_client()`:

```python
    def _complete_json_with_chat_completions(
        self,
        messages: list[ChatMessage],
    ) -> ChatCompletionResult:
        response = self._get_client().chat.completions.create(
            model=self.config.model,
            messages=[message.model_dump() for message in messages],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LLM response content is required")
        usage = getattr(response, "usage", None)
        return ChatCompletionResult(
            content=content,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )

    def _complete_json_with_responses(
        self,
        messages: list[ChatMessage],
    ) -> ChatCompletionResult:
        response = self._get_client().responses.create(
            model=self.config.model,
            input=[message.model_dump() for message in messages],
            text={"format": {"type": "json_object"}},
            temperature=0,
        )
        content = _extract_responses_content(response)
        usage = getattr(response, "usage", None)
        return ChatCompletionResult(
            content=content,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )
```

Add this helper below `_create_openai_client()`:

```python
def _extract_responses_content(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text
    raise ValueError("LLM response content is required")
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_llm_client.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add src/insight_graph/llm/client.py tests/test_llm_client.py
git commit -m "feat: support responses llm wire api"
```

---

### Task 3: Add Nested Responses Content Fallback

**Files:**
- Modify: `src/insight_graph/llm/client.py`
- Modify: `tests/test_llm_client.py`

- [ ] **Step 1: Add nested fake response helpers**

Add these helper classes after `FakeResponsesResponse` in `tests/test_llm_client.py`:

```python
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
```

Update `FakeOpenAIResponses.__init__()` signature from:

```python
    def __init__(
        self,
        output_text: str | None = '{"ok": true}',
        error: Exception | None = None,
        usage: FakeResponsesUsage | None = None,
    ) -> None:
```

to:

```python
    def __init__(
        self,
        output_text: str | None = '{"ok": true}',
        error: Exception | None = None,
        usage: FakeResponsesUsage | None = None,
        response: object | None = None,
    ) -> None:
```

Add `self.response = response` inside `__init__()`.

Update `FakeOpenAIResponses.create()` from:

```python
        return FakeResponsesResponse(self.output_text, usage=self.usage)
```

to:

```python
        if self.response is not None:
            return self.response
        return FakeResponsesResponse(self.output_text, usage=self.usage)
```

- [ ] **Step 2: Write failing nested output and empty response tests**

Add these tests after `test_openai_compatible_chat_client_maps_responses_usage()`:

```python
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
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_llm_client.py::test_openai_compatible_chat_client_reads_nested_responses_output_text tests/test_llm_client.py::test_openai_compatible_chat_client_requires_responses_content -q
```

Expected: first test FAILS because `_extract_responses_content()` only reads `output_text`; second test PASSES or FAILS with the same empty content error depending on the current helper implementation. The important RED check is that nested output text is not yet supported.

- [ ] **Step 4: Implement nested content extraction**

Replace `_extract_responses_content()` in `src/insight_graph/llm/client.py` with:

```python
def _extract_responses_content(response: Any) -> str:
    output_text = _get_attr_or_key(response, "output_text")
    if output_text:
        return output_text

    parts: list[str] = []
    for output_item in _get_attr_or_key(response, "output") or []:
        for content_item in _get_attr_or_key(output_item, "content") or []:
            text = _get_attr_or_key(content_item, "text")
            if text:
                parts.append(text)

    content = "".join(parts)
    if content:
        return content
    raise ValueError("LLM response content is required")


def _get_attr_or_key(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)
```

- [ ] **Step 5: Run client tests and lint**

Run:

```powershell
python -m pytest tests/test_llm_client.py -q
python -m ruff check src/insight_graph/llm/client.py tests/test_llm_client.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add src/insight_graph/llm/client.py tests/test_llm_client.py
git commit -m "test: cover responses output parsing"
```

---

### Task 4: Final Verification And Optional Live Smoke

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run focused LLM tests**

Run:

```powershell
python -m pytest tests/test_llm_config.py tests/test_llm_client.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full tests and lint**

Run:

```powershell
python -m pytest -q
python -m ruff check .
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 3: Run default live smoke to ensure no regression**

Run:

```powershell
$names = @("INSIGHT_GRAPH_LLM_API_KEY", "INSIGHT_GRAPH_LLM_BASE_URL", "INSIGHT_GRAPH_LLM_MODEL"); foreach ($name in $names) { $value = [Environment]::GetEnvironmentVariable($name, "User"); if (-not [string]::IsNullOrWhiteSpace($value)) { [Environment]::SetEnvironmentVariable($name, $value, "Process"); Set-Item -Path "env:$name" -Value $value } }; Remove-Item Env:\INSIGHT_GRAPH_LLM_WIRE_API -ErrorAction SilentlyContinue; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --output-json
```

Expected: workflow emits parseable JSON using default `chat_completions`; `llm_call_log` contains safe metadata and token fields when provider usage is returned.

- [ ] **Step 4: Run Responses live smoke if provider supports it**

Run:

```powershell
$names = @("INSIGHT_GRAPH_LLM_API_KEY", "INSIGHT_GRAPH_LLM_BASE_URL", "INSIGHT_GRAPH_LLM_MODEL"); foreach ($name in $names) { $value = [Environment]::GetEnvironmentVariable($name, "User"); if (-not [string]::IsNullOrWhiteSpace($value)) { [Environment]::SetEnvironmentVariable($name, $value, "Process"); Set-Item -Path "env:$name" -Value $value } }; $env:INSIGHT_GRAPH_LLM_WIRE_API = "responses"; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --output-json
```

Expected if the configured provider supports `/v1/responses`: workflow emits parseable JSON and `llm_call_log` contains safe metadata. If the provider does not support Responses API, record the provider error summary and do not treat it as a code regression if all fake-client tests pass.

- [ ] **Step 5: Inspect git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree on the implementation branch.
