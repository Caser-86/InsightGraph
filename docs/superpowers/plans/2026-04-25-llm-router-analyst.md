# LLM Router Analyst Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared OpenAI-compatible LLM layer and use it first as an opt-in Analyst provider while preserving deterministic/offline defaults.

**Architecture:** Create focused `llm` modules for config, client, and router; refactor relevance to reuse the shared layer; then add an LLM Analyst path with strict JSON parsing and deterministic fallback. Tests use fake clients only and never call live providers.

**Tech Stack:** Python 3.11+, Pydantic, OpenAI Python SDK, Pytest, Ruff.

---

## File Structure

- Create: `src/insight_graph/llm/__init__.py` - package exports for LLM config, client, and router.
- Create: `src/insight_graph/llm/config.py` - shared `LLMConfig` and env resolution.
- Create: `src/insight_graph/llm/client.py` - `ChatMessage`, `ChatCompletionClient`, and `OpenAICompatibleChatClient`.
- Create: `src/insight_graph/llm/router.py` - small factory returning the OpenAI-compatible client.
- Create: `tests/test_llm_config.py` - config precedence tests.
- Create: `tests/test_llm_client.py` - fake OpenAI chat completions tests.
- Modify: `src/insight_graph/agents/relevance.py` - reuse shared config/client while preserving behavior.
- Modify: `tests/test_relevance.py` - update imports and fake factory expectations after the refactor.
- Modify: `src/insight_graph/agents/analyst.py` - add opt-in LLM Analyst provider with deterministic fallback.
- Modify: `tests/test_agents.py` - add LLM Analyst fake-client and fallback tests.
- Modify: `README.md` - document Analyst LLM provider env vars and defaults.

---

### Task 1: Shared LLM Config And Client

**Files:**
- Create: `src/insight_graph/llm/__init__.py`
- Create: `src/insight_graph/llm/config.py`
- Create: `src/insight_graph/llm/client.py`
- Create: `src/insight_graph/llm/router.py`
- Create: `tests/test_llm_config.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: Add failing config tests**

Create `tests/test_llm_config.py`:

```python
from insight_graph.llm.config import resolve_llm_config


def test_resolve_llm_config_prefers_insight_graph_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "ig-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    config = resolve_llm_config()

    assert config.api_key == "ig-key"
    assert config.base_url == "https://relay.example/v1"
    assert config.model == "relay-model"


def test_resolve_llm_config_falls_back_to_openai_env(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    config = resolve_llm_config()

    assert config.api_key == "openai-key"
    assert config.base_url == "https://api.openai.com/v1"
    assert config.model == "gpt-4o-mini"


def test_resolve_llm_config_explicit_args_override_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "ig-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")

    config = resolve_llm_config(
        api_key="explicit-key",
        base_url="https://explicit.example/v1",
        model="explicit-model",
    )

    assert config.api_key == "explicit-key"
    assert config.base_url == "https://explicit.example/v1"
    assert config.model == "explicit-model"
```

- [ ] **Step 2: Run config tests to verify they fail**

Run: `python -m pytest tests/test_llm_config.py -v`

Expected: FAIL with `ModuleNotFoundError` for `insight_graph.llm`.

- [ ] **Step 3: Add config implementation**

Create `src/insight_graph/llm/__init__.py`:

```python
from insight_graph.llm.client import ChatCompletionClient, ChatMessage, OpenAICompatibleChatClient
from insight_graph.llm.config import LLMConfig, resolve_llm_config
from insight_graph.llm.router import get_llm_client

__all__ = [
    "ChatCompletionClient",
    "ChatMessage",
    "LLMConfig",
    "OpenAICompatibleChatClient",
    "get_llm_client",
    "resolve_llm_config",
]
```

Create `src/insight_graph/llm/config.py`:

```python
import os

from pydantic import BaseModel


class LLMConfig(BaseModel):
    api_key: str | None
    base_url: str | None
    model: str


def resolve_llm_config(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
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
    )
```

- [ ] **Step 4: Run config tests to verify they pass**

Run: `python -m pytest tests/test_llm_config.py -v`

Expected: 3 passed.

- [ ] **Step 5: Add failing client tests**

Create `tests/test_llm_client.py`:

```python
import pytest

from insight_graph.llm.client import ChatMessage, OpenAICompatibleChatClient
from insight_graph.llm.config import LLMConfig
from insight_graph.llm.router import get_llm_client


class FakeOpenAIMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class FakeOpenAIChoice:
    def __init__(self, content: str | None) -> None:
        self.message = FakeOpenAIMessage(content)


class FakeOpenAIResponse:
    def __init__(self, content: str | None) -> None:
        self.choices = [FakeOpenAIChoice(content)]


class FakeOpenAICompletions:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return FakeOpenAIResponse(self.content)


class FakeOpenAIChat:
    def __init__(self, completions: FakeOpenAICompletions) -> None:
        self.completions = completions


class FakeOpenAIClient:
    def __init__(self, completions: FakeOpenAICompletions) -> None:
        self.chat = FakeOpenAIChat(completions)


def test_openai_compatible_chat_client_completes_json() -> None:
    completions = FakeOpenAICompletions('{"ok": true}')
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key="test-key", base_url="https://relay.example/v1", model="relay-model"),
        client=FakeOpenAIClient(completions),
    )
    messages = [
        ChatMessage(role="system", content="Return JSON."),
        ChatMessage(role="user", content="Analyze evidence."),
    ]

    content = client.complete_json(messages)

    assert content == '{"ok": true}'
    assert completions.calls == [
        {
            "model": "relay-model",
            "messages": [
                {"role": "system", "content": "Return JSON."},
                {"role": "user", "content": "Analyze evidence."},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
    ]


def test_openai_compatible_chat_client_uses_factory_with_base_url() -> None:
    completions = FakeOpenAICompletions('{"ok": true}')
    calls = []

    def fake_factory(api_key: str, base_url: str | None):
        calls.append((api_key, base_url))
        return FakeOpenAIClient(completions)

    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key="factory-key", base_url="https://relay.example/v1", model="model"),
        client_factory=fake_factory,
    )

    content = client.complete_json([ChatMessage(role="user", content="Return JSON.")])

    assert content == '{"ok": true}'
    assert calls == [("factory-key", "https://relay.example/v1")]


def test_openai_compatible_chat_client_requires_api_key() -> None:
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key=None, base_url=None, model="model")
    )

    with pytest.raises(ValueError, match="missing an API key"):
        client.complete_json([ChatMessage(role="user", content="Return JSON.")])


def test_openai_compatible_chat_client_propagates_api_error() -> None:
    completions = FakeOpenAICompletions(error=RuntimeError("relay unavailable"))
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key="test-key", base_url=None, model="model"),
        client=FakeOpenAIClient(completions),
    )

    with pytest.raises(RuntimeError, match="relay unavailable"):
        client.complete_json([ChatMessage(role="user", content="Return JSON.")])


def test_get_llm_client_returns_openai_compatible_client() -> None:
    config = LLMConfig(api_key="test-key", base_url=None, model="model")

    client = get_llm_client(config)

    assert isinstance(client, OpenAICompatibleChatClient)


def test_llm_package_exports_core_types() -> None:
    from insight_graph.llm import LLMConfig as ExportedLLMConfig

    assert ExportedLLMConfig is LLMConfig
```

- [ ] **Step 6: Run client tests to verify they fail**

Run: `python -m pytest tests/test_llm_client.py -v`

Expected: FAIL because `client.py` and `router.py` are not implemented.

- [ ] **Step 7: Add client and router implementation**

Create `src/insight_graph/llm/client.py`:

```python
from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel

from insight_graph.llm.config import LLMConfig, resolve_llm_config


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionClient(Protocol):
    def complete_json(self, messages: list[ChatMessage]) -> str: ...


class OpenAICompatibleChatClient:
    def __init__(
        self,
        config: LLMConfig | None = None,
        client: Any | None = None,
        client_factory: Callable[[str, str | None], Any] | None = None,
    ) -> None:
        self._config = config or resolve_llm_config()
        self._client = client
        self._client_factory = client_factory or _create_openai_client

    def complete_json(self, messages: list[ChatMessage]) -> str:
        if not self._config.api_key:
            raise ValueError("OpenAI-compatible LLM client is missing an API key.")
        client = self._client or self._client_factory(
            self._config.api_key,
            self._config.base_url,
        )
        response = client.chat.completions.create(
            model=self._config.model,
            messages=[message.model_dump() for message in messages],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("OpenAI-compatible LLM client returned empty content.")
        return content


def _create_openai_client(api_key: str, base_url: str | None) -> Any:
    from openai import OpenAI

    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)
```

Create `src/insight_graph/llm/router.py`:

```python
from insight_graph.llm.client import ChatCompletionClient, OpenAICompatibleChatClient
from insight_graph.llm.config import LLMConfig


def get_llm_client(config: LLMConfig | None = None) -> ChatCompletionClient:
    return OpenAICompatibleChatClient(config=config)
```

- [ ] **Step 8: Run LLM tests and lint**

Run: `python -m pytest tests/test_llm_config.py tests/test_llm_client.py -v`

Expected: 9 passed.

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 9: Commit**

```bash
git add src/insight_graph/llm tests/test_llm_config.py tests/test_llm_client.py
git commit -m "feat: add openai compatible llm client"
```

---

### Task 2: Relevance Judge Uses Shared LLM Layer

**Files:**
- Modify: `src/insight_graph/agents/relevance.py`
- Modify: `tests/test_relevance.py`

- [ ] **Step 1: Update relevance imports test expectations**

Modify the import block in `tests/test_relevance.py` from:

```python
from insight_graph.agents.relevance import (
    DeterministicRelevanceJudge,
    EvidenceRelevanceDecision,
    OpenAICompatibleRelevanceJudge,
    _resolve_openai_compatible_config,
    filter_relevant_evidence,
    get_relevance_judge,
    is_relevance_filter_enabled,
)
```

to:

```python
from insight_graph.agents.relevance import (
    DeterministicRelevanceJudge,
    EvidenceRelevanceDecision,
    OpenAICompatibleRelevanceJudge,
    filter_relevant_evidence,
    get_relevance_judge,
    is_relevance_filter_enabled,
)
from insight_graph.llm.config import resolve_llm_config
```

Replace `config = _resolve_openai_compatible_config()` in both config tests with:

```python
    config = resolve_llm_config()
```

- [ ] **Step 2: Run relevance tests to verify they still pass before refactor**

Run: `python -m pytest tests/test_relevance.py -v`

Expected: all relevance tests pass. This confirms the test import migration did not change behavior.

- [ ] **Step 3: Refactor relevance to use shared config/client**

Modify `src/insight_graph/agents/relevance.py` imports.

Replace:

```python
from collections.abc import Callable
from typing import Any, Protocol
```

with:

```python
from typing import Protocol
```

Add:

```python
from insight_graph.llm.client import ChatCompletionClient, ChatMessage, OpenAICompatibleChatClient
from insight_graph.llm.config import resolve_llm_config
```

Delete the local `OpenAICompatibleConfig` class.

Replace `OpenAICompatibleRelevanceJudge.__init__` and `judge` with:

```python
class OpenAICompatibleRelevanceJudge:
    def __init__(
        self,
        client: ChatCompletionClient | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        client_factory=None,
    ) -> None:
        config = resolve_llm_config(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        self._config = config
        self._client = client or OpenAICompatibleChatClient(
            config=config,
            client_factory=client_factory,
        )

    def judge(
        self,
        query: str,
        subtask: Subtask,
        evidence: Evidence,
    ) -> EvidenceRelevanceDecision:
        if not self._config.api_key:
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="OpenAI-compatible relevance judge is missing an API key.",
            )

        try:
            content = self._client.complete_json(_build_relevance_messages(query, subtask, evidence))
            return _parse_relevance_json(content, evidence.id)
        except ValueError:
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="OpenAI-compatible relevance judge returned invalid JSON.",
            )
        except Exception as exc:
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason=f"OpenAI-compatible relevance judge failed: {exc}",
            )
```

Delete the local `_resolve_openai_compatible_config` and `_create_openai_client` helpers.

Change `_build_relevance_messages` return type and body from `list[dict[str, str]]` to `list[ChatMessage]`:

```python
def _build_relevance_messages(
    query: str,
    subtask: Subtask,
    evidence: Evidence,
) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="system",
            content=(
                "You judge whether evidence is relevant to a research query and subtask. "
                "Return only JSON with boolean field relevant and string field reason."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Query: {query}\n"
                f"Subtask ID: {subtask.id}\n"
                f"Subtask description: {subtask.description}\n"
                f"Evidence ID: {evidence.id}\n"
                f"Evidence title: {evidence.title}\n"
                f"Evidence source URL: {evidence.source_url}\n"
                f"Evidence verified: {evidence.verified}\n"
                f"Evidence snippet: {evidence.snippet}"
            ),
        ),
    ]
```

- [ ] **Step 4: Update fake relevance client tests**

The fake OpenAI client classes in `tests/test_relevance.py` can stay. Add this fake chat completion client after `FakeOpenAIClient`:

```python
class FakeChatCompletionClient:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.messages = []

    def complete_json(self, messages):
        self.messages.append(messages)
        if self.error is not None:
            raise self.error
        return self.content
```

Keep the factory/base URL test using `FakeOpenAIClient` because it verifies `OpenAICompatibleChatClient` factory wiring through the relevance judge.

In these tests, replace `client=FakeOpenAIClient(completions)` with `client=FakeChatCompletionClient(...)` and adjust assertions:

- `test_openai_compatible_judge_keeps_relevant_json_response`
- `test_openai_compatible_judge_filters_false_json_response`
- `test_openai_compatible_judge_fails_closed_for_api_error`
- `test_openai_compatible_judge_fails_closed_for_invalid_json`
- `test_openai_compatible_judge_fails_closed_for_invalid_schema`

For `test_openai_compatible_judge_keeps_relevant_json_response`, use:

```python
    client = FakeChatCompletionClient(
        '{"relevant": true, "reason": "Evidence directly matches the query."}'
    )
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
        model="relay-model",
    )
```

Replace the completions call assertions with:

```python
    messages = client.messages[0]
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert "Compare AI coding agents" in messages[1].content
    assert "Cursor Pricing" in messages[1].content
```

For the API error test, use:

```python
    client = FakeChatCompletionClient(error=RuntimeError("relay unavailable"))
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
    )
```

- [ ] **Step 5: Run relevance and LLM tests**

Run: `python -m pytest tests/test_relevance.py tests/test_llm_config.py tests/test_llm_client.py -v`

Expected: all selected tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/agents/relevance.py tests/test_relevance.py
git commit -m "refactor: reuse shared llm client for relevance"
```

---

### Task 3: Opt-In LLM Analyst Provider

**Files:**
- Modify: `src/insight_graph/agents/analyst.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Add failing Analyst provider tests**

Modify the import in `tests/test_agents.py` from:

```python
from insight_graph.agents.analyst import analyze_evidence
```

to:

```python
import pytest

from insight_graph.agents.analyst import analyze_evidence, get_analyst_provider
```

Keep the existing imports for `collect_evidence`, `critique_analysis`, `plan_research`, `write_report`, `Evidence`, `Finding`, and `GraphState` below these lines.

Append these helpers and tests to `tests/test_agents.py`:

```python

class FakeLLMClient:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.messages = []

    def complete_json(self, messages):
        self.messages.append(messages)
        if self.error is not None:
            raise self.error
        return self.content


def make_analyst_state() -> GraphState:
    return GraphState(
        user_request="Compare Cursor and GitHub Copilot",
        evidence_pool=[
            Evidence(
                id="cursor-pricing",
                subtask_id="collect",
                title="Cursor Pricing",
                source_url="https://cursor.com/pricing",
                snippet="Cursor has Pro and Business plans.",
                source_type="official_site",
                verified=True,
            ),
            Evidence(
                id="copilot-docs",
                subtask_id="collect",
                title="GitHub Copilot Docs",
                source_url="https://docs.github.com/copilot",
                snippet="Copilot supports coding assistance in GitHub and IDEs.",
                source_type="docs",
                verified=True,
            ),
        ],
    )


def test_get_analyst_provider_defaults_to_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_ANALYST_PROVIDER", raising=False)

    assert get_analyst_provider() == "deterministic"


def test_get_analyst_provider_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown analyst provider"):
        get_analyst_provider("unknown")


def test_analyze_evidence_uses_llm_provider_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    client = FakeLLMClient(
        '{"findings": [{"title": "Pricing differs", "summary": "Cursor and Copilot package coding assistance differently.", "evidence_ids": ["cursor-pricing", "copilot-docs"]}]}'
    )
    state = make_analyst_state()

    updated = analyze_evidence(state, llm_client=client)

    assert updated.findings == [
        Finding(
            title="Pricing differs",
            summary="Cursor and Copilot package coding assistance differently.",
            evidence_ids=["cursor-pricing", "copilot-docs"],
        )
    ]
    assert len(client.messages) == 1
    assert client.messages[0][0].role == "system"
    assert "Compare Cursor and GitHub Copilot" in client.messages[0][1].content
    assert "cursor-pricing" in client.messages[0][1].content


def test_analyze_evidence_falls_back_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    state = make_analyst_state()

    updated = analyze_evidence(state)

    assert [finding.title for finding in updated.findings] == [
        "Official sources establish baseline product positioning",
        "Open repositories add adoption and roadmap signals",
    ]


@pytest.mark.parametrize(
    "content",
    [
        None,
        "not json",
        "{}",
        '{"findings": []}',
        '{"findings": [{"title": "Bad", "summary": "Missing evidence", "evidence_ids": ["missing"]}]}',
    ],
)
def test_analyze_evidence_falls_back_for_invalid_llm_output(monkeypatch, content: str | None) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    client = FakeLLMClient(content)
    state = make_analyst_state()

    updated = analyze_evidence(state, llm_client=client)

    assert [finding.title for finding in updated.findings] == [
        "Official sources establish baseline product positioning",
        "Open repositories add adoption and roadmap signals",
    ]


def test_analyze_evidence_falls_back_for_unverified_citation(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    client = FakeLLMClient(
        '{"findings": [{"title": "Bad citation", "summary": "Uses unverified evidence.", "evidence_ids": ["unverified-source"]}]}'
    )
    state = make_analyst_state()
    state.evidence_pool.append(
        Evidence(
            id="unverified-source",
            subtask_id="collect",
            title="Unverified Source",
            source_url="https://example.com/unverified",
            snippet="Unverified snippet.",
            verified=False,
        )
    )

    updated = analyze_evidence(state, llm_client=client)

    assert [finding.title for finding in updated.findings] == [
        "Official sources establish baseline product positioning",
        "Open repositories add adoption and roadmap signals",
    ]


def test_analyze_evidence_falls_back_for_llm_error(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    client = FakeLLMClient(error=RuntimeError("relay unavailable"))
    state = make_analyst_state()

    updated = analyze_evidence(state, llm_client=client)

    assert [finding.title for finding in updated.findings] == [
        "Official sources establish baseline product positioning",
        "Open repositories add adoption and roadmap signals",
    ]
```

- [ ] **Step 2: Run Analyst tests to verify they fail**

Run: `python -m pytest tests/test_agents.py -v`

Expected: FAIL because `get_analyst_provider` and `llm_client` support are missing.

- [ ] **Step 3: Implement LLM Analyst**

Replace `src/insight_graph/agents/analyst.py` with:

```python
import json
import os

from insight_graph.llm.client import ChatCompletionClient, ChatMessage
from insight_graph.llm.config import resolve_llm_config
from insight_graph.llm.router import get_llm_client
from insight_graph.state import Evidence, Finding, GraphState


def analyze_evidence(
    state: GraphState,
    llm_client: ChatCompletionClient | None = None,
) -> GraphState:
    provider = get_analyst_provider()
    if provider == "deterministic":
        return _analyze_evidence_deterministic(state)
    try:
        return _analyze_evidence_with_llm(state, llm_client)
    except Exception:
        return _analyze_evidence_deterministic(state)


def get_analyst_provider(name: str | None = None) -> str:
    provider = (name or os.getenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "deterministic")).lower()
    if provider in {"deterministic", "llm"}:
        return provider
    raise ValueError(f"Unknown analyst provider: {provider}")


def _analyze_evidence_deterministic(state: GraphState) -> GraphState:
    evidence_ids = [item.id for item in state.evidence_pool]
    state.findings = [
        Finding(
            title="Official sources establish baseline product positioning",
            summary=(
                "Official pricing pages, documentation, and repositories provide the safest "
                "baseline for comparing product positioning and capabilities."
            ),
            evidence_ids=evidence_ids[:2],
        ),
        Finding(
            title="Open repositories add adoption and roadmap signals",
            summary=(
                "GitHub evidence helps evaluate public development activity, release cadence, "
                "and community-facing positioning."
            ),
            evidence_ids=evidence_ids[2:],
        ),
    ]
    return state


def _analyze_evidence_with_llm(
    state: GraphState,
    llm_client: ChatCompletionClient | None,
) -> GraphState:
    config = resolve_llm_config()
    if llm_client is None and not config.api_key:
        raise ValueError("LLM analyst is missing an API key.")
    client = llm_client or get_llm_client(config)
    content = client.complete_json(_build_analyst_messages(state))
    state.findings = _parse_analyst_findings(content, state.evidence_pool)
    return state


def _build_analyst_messages(state: GraphState) -> list[ChatMessage]:
    evidence_lines = []
    for item in state.evidence_pool:
        if not item.verified:
            continue
        evidence_lines.append(
            "\n".join(
                [
                    f"Evidence ID: {item.id}",
                    f"Title: {item.title}",
                    f"Source URL: {item.source_url}",
                    f"Source type: {item.source_type}",
                    f"Snippet: {item.snippet}",
                ]
            )
        )
    evidence_text = "\n\n".join(evidence_lines)
    return [
        ChatMessage(
            role="system",
            content=(
                "You are an evidence-grounded business intelligence analyst. "
                "Return only JSON with a non-empty findings array. Each finding must include "
                "title, summary, and evidence_ids. Use only evidence IDs provided by the user."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Research request: {state.user_request}\n\n"
                "Verified evidence:\n"
                f"{evidence_text}\n\n"
                "Return JSON shaped like: "
                '{"findings":[{"title":"...","summary":"...","evidence_ids":["..."]}]}'
            ),
        ),
    ]


def _parse_analyst_findings(content: str | None, evidence_pool: list[Evidence]) -> list[Finding]:
    if not content:
        raise ValueError("LLM analyst returned empty content.")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("LLM analyst returned non-object JSON.")
    findings_data = parsed.get("findings")
    if not isinstance(findings_data, list) or not findings_data:
        raise ValueError("LLM analyst returned no findings.")

    verified_ids = {item.id for item in evidence_pool if item.verified}
    findings: list[Finding] = []
    for item in findings_data:
        if not isinstance(item, dict):
            raise ValueError("LLM analyst finding is not an object.")
        title = item.get("title")
        summary = item.get("summary")
        evidence_ids = item.get("evidence_ids")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("LLM analyst finding title is invalid.")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("LLM analyst finding summary is invalid.")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise ValueError("LLM analyst finding evidence IDs are invalid.")
        if not all(isinstance(evidence_id, str) for evidence_id in evidence_ids):
            raise ValueError("LLM analyst finding evidence IDs must be strings.")
        if not set(evidence_ids).issubset(verified_ids):
            raise ValueError("LLM analyst referenced missing or unverified evidence.")
        findings.append(
            Finding(
                title=title,
                summary=summary,
                evidence_ids=evidence_ids,
            )
        )
    return findings
```

- [ ] **Step 4: Run Analyst tests**

Run: `python -m pytest tests/test_agents.py -v`

Expected: all agent tests pass.

- [ ] **Step 5: Run graph and CLI tests to confirm defaults**

Run: `python -m pytest tests/test_graph.py tests/test_cli.py -v`

Expected: all selected tests pass without LLM env vars.

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/agents/analyst.py tests/test_agents.py
git commit -m "feat: add opt-in llm analyst"
```

---

### Task 4: Documentation And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README feature table**

In `README.md`, replace this row:

```markdown
| Critic | 已实现证据数量、分析结果、citation support 检查；失败路径最多重试一次后输出失败评估 |
```

with:

```markdown
| Critic | 已实现证据数量、分析结果、citation support 检查；失败路径最多重试一次后输出失败评估 |
| Analyst | 默认 deterministic/offline；可通过 `INSIGHT_GRAPH_ANALYST_PROVIDER=llm` opt-in 使用 OpenAI-compatible LLM 生成 evidence-grounded findings |
```

- [ ] **Step 2: Add Analyst LLM configuration docs**

After the OpenAI-compatible relevance relay example block, add:

````markdown

### LLM Analyst 配置

Analyst 默认继续使用 deterministic/offline 逻辑，不调用真实 LLM。需要让 Analyst 使用 OpenAI-compatible 模型生成 findings 时，可显式启用：

```bash
INSIGHT_GRAPH_ANALYST_PROVIDER=llm \
INSIGHT_GRAPH_LLM_API_KEY=sk-your-relay-key \
INSIGHT_GRAPH_LLM_BASE_URL=https://relay.example.com/v1 \
INSIGHT_GRAPH_LLM_MODEL=gpt-4o-mini \
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_ANALYST_PROVIDER` | `deterministic` 或 `llm` | `deterministic` |
| `INSIGHT_GRAPH_LLM_API_KEY` | OpenAI-compatible provider API key；未设置时回退到 `OPENAI_API_KEY` | - |
| `INSIGHT_GRAPH_LLM_BASE_URL` | OpenAI-compatible `/v1` endpoint；未设置时回退到 `OPENAI_BASE_URL` | - |
| `INSIGHT_GRAPH_LLM_MODEL` | OpenAI-compatible Analyst model | `gpt-4o-mini` |

LLM Analyst 只接受引用当前 verified evidence ID 的 JSON findings。缺少 API key、API 调用失败、JSON 无效、schema 不合法、引用不存在或引用未 verified evidence 时，会回退到 deterministic Analyst。测试默认不调用外部 LLM。
````

- [ ] **Step 3: Run README grep check**

Run: `python -m pytest tests/test_cli.py -v`

Expected: CLI tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 4: Run final verification**

Run: `python -m pytest -v`

Expected: all tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

Run: `python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"`

Expected: output includes `# InsightGraph Research Report`, `## Key Findings`, and `## References`. Do not set `INSIGHT_GRAPH_ANALYST_PROVIDER=llm` for this smoke test.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document llm analyst provider"
```

---

## Self-Review

- Spec coverage: This plan adds shared LLM config/client/router modules, refactors relevance to reuse them, adds opt-in LLM Analyst with deterministic fallback, documents the new env vars, and preserves offline defaults.
- Deferred scope: Native non-OpenAI SDKs, streaming, token budgets, Planner/Reporter/Critic LLM integration, tracing, and persistence remain excluded.
- Placeholder scan: No placeholder instructions remain; every task includes concrete files, code, commands, expected failures, expected passing checks, and commit messages.
- Type consistency: `LLMConfig`, `resolve_llm_config`, `ChatMessage`, `ChatCompletionClient`, `OpenAICompatibleChatClient`, `get_llm_client`, `get_analyst_provider`, and `INSIGHT_GRAPH_ANALYST_PROVIDER` are named consistently across tasks.
