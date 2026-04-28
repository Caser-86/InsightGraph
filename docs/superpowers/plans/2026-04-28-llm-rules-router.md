# LLM Rules Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in internal rules router that selects user-defined fast/default/strong LLM models by purpose and prompt size.

**Architecture:** Keep `get_llm_client()` as the public factory. Add pure routing helpers in `src/insight_graph/llm/router.py` that copy `LLMConfig` with a selected model, then return the existing `OpenAICompatibleChatClient`. Analyst and reporter pass purpose/messages when they create their own client; injected clients remain unchanged.

**Tech Stack:** Python 3.13 local, Python 3.11 CI, OpenAI-compatible client, Pydantic, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/llm/router.py`: routing env parsing, tier fallback, message-size rules, and `get_llm_client()` context parameters.
- Modify `src/insight_graph/agents/analyst.py`: build messages before client creation and pass `purpose="analyst"` plus messages.
- Modify `src/insight_graph/agents/reporter.py`: build messages before client creation and pass `purpose="reporter"` plus messages.
- Create `tests/test_llm_router.py`: pure unit tests for routing rules and config preservation.
- Modify `tests/test_agents.py`: targeted call-site tests proving analyst/reporter pass purpose and messages when creating clients.
- Modify `docs/configuration.md`: document env vars and LiteLLM Proxy usage through `INSIGHT_GRAPH_LLM_BASE_URL`.

## Task 1: Pure Router Rules

**Files:**
- Create: `tests/test_llm_router.py`
- Modify: `src/insight_graph/llm/router.py`

- [ ] **Step 1: Write failing router tests**

Create `tests/test_llm_router.py` with:

```python
import pytest

from insight_graph.llm import ChatMessage, LLMConfig, OpenAICompatibleChatClient, get_llm_client
from insight_graph.llm.router import select_llm_model


def base_config(model: str = "base-model") -> LLMConfig:
    return LLMConfig(
        api_key="test-key",
        base_url="https://relay.example/v1",
        model=model,
        wire_api="responses",
    )


def test_get_llm_client_preserves_model_when_router_disabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_ROUTER", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    client = get_llm_client(config=base_config("configured-model"))

    assert isinstance(client, OpenAICompatibleChatClient)
    assert client.config.model == "configured-model"
    assert client.config.api_key == "test-key"
    assert client.config.base_url == "https://relay.example/v1"
    assert client.config.wire_api == "responses"


def test_rules_router_selects_fast_for_short_default_prompt(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_FAST", "fast-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    selected = select_llm_model(
        base_config("base-model"),
        purpose="default",
        messages=[ChatMessage(role="user", content="short")],
    )

    assert selected == "fast-model"


def test_rules_router_selects_default_for_medium_default_prompt(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_FAST", "fast-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_FAST_CHAR_THRESHOLD", "3")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD", "100")

    selected = select_llm_model(
        base_config("base-model"),
        purpose="default",
        messages=[ChatMessage(role="user", content="medium")],
    )

    assert selected == "default-model"


def test_rules_router_selects_strong_for_long_default_prompt(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD", "10")

    selected = select_llm_model(
        base_config("base-model"),
        purpose="default",
        messages=[ChatMessage(role="user", content="x" * 11)],
    )

    assert selected == "strong-model"


def test_rules_router_selects_reporter_strong_without_messages(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    assert select_llm_model(base_config("base-model"), purpose="reporter") == "strong-model"


def test_rules_router_selects_analyst_default_for_short_prompt(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_FAST", "fast-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    selected = select_llm_model(
        base_config("base-model"),
        purpose="analyst",
        messages=[ChatMessage(role="user", content="short")],
    )

    assert selected == "default-model"


def test_rules_router_selects_analyst_strong_for_long_prompt(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD", "10")

    selected = select_llm_model(
        base_config("base-model"),
        purpose="analyst",
        messages=[ChatMessage(role="user", content="x" * 11)],
    )

    assert selected == "strong-model"


def test_rules_router_falls_back_missing_tier_models(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL_FAST", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", raising=False)

    assert select_llm_model(base_config("base-model"), purpose="default") == "base-model"
    assert select_llm_model(base_config("base-model"), purpose="reporter") == "base-model"


def test_get_llm_client_preserves_non_model_config_when_router_enabled(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    client = get_llm_client(config=base_config("base-model"), purpose="reporter")

    assert client.config.model == "strong-model"
    assert client.config.api_key == "test-key"
    assert client.config.base_url == "https://relay.example/v1"
    assert client.config.wire_api == "responses"


def test_rules_router_rejects_unknown_router(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "mystery")

    with pytest.raises(ValueError, match="Unsupported LLM router"):
        select_llm_model(base_config("base-model"), purpose="default")


def test_rules_router_rejects_invalid_threshold(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD", "not-an-int")

    with pytest.raises(ValueError, match="INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD"):
        select_llm_model(base_config("base-model"), purpose="default")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_router.py -v
```

Expected: FAIL because `select_llm_model()` does not exist and `get_llm_client()` does not accept routing context.

- [ ] **Step 3: Implement router helpers**

Replace `src/insight_graph/llm/router.py` with:

```python
from __future__ import annotations

import os

from insight_graph.llm.client import ChatMessage, OpenAICompatibleChatClient
from insight_graph.llm.config import LLMConfig, resolve_llm_config

DEFAULT_FAST_CHAR_THRESHOLD = 2000
DEFAULT_STRONG_CHAR_THRESHOLD = 12000
LLM_ROUTER_DISABLED = ""
LLM_ROUTER_RULES = "rules"
SUPPORTED_LLM_ROUTERS = {LLM_ROUTER_DISABLED, LLM_ROUTER_RULES}


def get_llm_client(
    config: LLMConfig | None = None,
    *,
    purpose: str = "default",
    messages: list[ChatMessage] | None = None,
) -> OpenAICompatibleChatClient:
    resolved = config or resolve_llm_config()
    selected_model = select_llm_model(resolved, purpose=purpose, messages=messages)
    if selected_model != resolved.model:
        resolved = resolved.model_copy(update={"model": selected_model})
    return OpenAICompatibleChatClient(config=resolved)


def select_llm_model(
    config: LLMConfig,
    *,
    purpose: str = "default",
    messages: list[ChatMessage] | None = None,
) -> str:
    router = os.getenv("INSIGHT_GRAPH_LLM_ROUTER", LLM_ROUTER_DISABLED).strip().lower()
    if router not in SUPPORTED_LLM_ROUTERS:
        raise ValueError(f"Unsupported LLM router: {router}")
    if router != LLM_ROUTER_RULES:
        return config.model

    fast_model = _tier_model("INSIGHT_GRAPH_LLM_MODEL_FAST", config.model)
    default_model = _tier_model("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", config.model)
    strong_model = _tier_model("INSIGHT_GRAPH_LLM_MODEL_STRONG", default_model)
    message_chars = _message_char_count(messages)
    fast_threshold = _int_env(
        "INSIGHT_GRAPH_LLM_ROUTER_FAST_CHAR_THRESHOLD",
        DEFAULT_FAST_CHAR_THRESHOLD,
    )
    strong_threshold = _int_env(
        "INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD",
        DEFAULT_STRONG_CHAR_THRESHOLD,
    )

    if purpose == "reporter":
        return strong_model
    if message_chars is not None and message_chars > strong_threshold:
        return strong_model
    if purpose == "default" and message_chars is not None and message_chars <= fast_threshold:
        return fast_model
    return default_model


def _tier_model(env_name: str, fallback: str) -> str:
    return os.getenv(env_name) or fallback


def _message_char_count(messages: list[ChatMessage] | None) -> int | None:
    if messages is None:
        return None
    return sum(len(message.content) for message in messages)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value
```

- [ ] **Step 4: Run router tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_router.py -v
```

Expected: all router tests pass.

- [ ] **Step 5: Run existing LLM client tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_client.py tests/test_llm_config.py -v
```

Expected: existing LLM config/client tests pass.

- [ ] **Step 6: Commit router rules**

```powershell
git add src/insight_graph/llm/router.py tests/test_llm_router.py
git commit -m "feat: add llm rules router"
```

## Task 2: Analyst and Reporter Call Sites

**Files:**
- Modify: `tests/test_agents.py`
- Modify: `src/insight_graph/agents/analyst.py`
- Modify: `src/insight_graph/agents/reporter.py`

- [ ] **Step 1: Write failing call-site tests**

Add this helper class near existing fake LLM client helpers in `tests/test_agents.py`:

```python
class RecordingRouterClient(FakeLLMClient):
    def __init__(self, content: str) -> None:
        super().__init__(content=content)
```

Append these tests near the LLM analyst/reporter tests:

```python
def test_llm_analyst_creates_client_with_routing_context(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "test-key")
    calls: list[dict] = []

    def fake_get_llm_client(config=None, *, purpose="default", messages=None):
        calls.append({"config": config, "purpose": purpose, "messages": messages})
        return RecordingRouterClient(
            '{"findings": [{"title": "Pricing differs", '
            '"summary": "Cursor and Copilot differ.", '
            '"evidence_ids": ["cursor-pricing"]}]}'
        )

    monkeypatch.setattr("insight_graph.agents.analyst.get_llm_client", fake_get_llm_client)

    updated = analyze_evidence(make_analyst_state())

    assert updated.findings[0].title == "Pricing differs"
    assert len(calls) == 1
    assert calls[0]["purpose"] == "analyst"
    assert calls[0]["messages"] is not None
    assert "cursor-pricing" in calls[0]["messages"][-1].content


def test_llm_reporter_creates_client_with_routing_context(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "test-key")
    calls: list[dict] = []

    def fake_get_llm_client(config=None, *, purpose="default", messages=None):
        calls.append({"config": config, "purpose": purpose, "messages": messages})
        return RecordingRouterClient(
            '{"markdown":"# InsightGraph Research Report\\n\\n## Key Findings\\n\\n'
            'Cursor differs from Copilot [1]."}'
        )

    monkeypatch.setattr("insight_graph.agents.reporter.get_llm_client", fake_get_llm_client)

    updated = write_report(make_reporter_state())

    assert "Cursor differs from Copilot [1]." in updated.report_markdown
    assert len(calls) == 1
    assert calls[0]["purpose"] == "reporter"
    assert calls[0]["messages"] is not None
    assert "allowed_citations" in calls[0]["messages"][-1].content
```

- [ ] **Step 2: Run call-site tests to verify they fail**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py::test_llm_analyst_creates_client_with_routing_context tests/test_agents.py::test_llm_reporter_creates_client_with_routing_context -v
```

Expected: FAIL because call sites create clients before messages and do not pass `purpose` or `messages`.

- [ ] **Step 3: Update analyst call site**

In `src/insight_graph/agents/analyst.py`, change `_analyze_evidence_with_llm()` so messages are built before client creation:

```python
def _analyze_evidence_with_llm(
    state: GraphState,
    llm_client: ChatCompletionClient | None = None,
) -> GraphState:
    config = resolve_llm_config()
    messages = _build_analyst_messages(state)
    if llm_client is None:
        if not config.api_key:
            raise ValueError("LLM api_key is required")
        llm_client = get_llm_client(config, purpose="analyst", messages=messages)

    wire_api = get_llm_wire_api(llm_client)
    started = time.perf_counter()
```

Remove the duplicate `messages = _build_analyst_messages(state)` line that appears after client creation.

- [ ] **Step 4: Update reporter call site**

In `src/insight_graph/agents/reporter.py`, change `_write_report_with_llm()` so messages are built before client creation:

```python
    config = resolve_llm_config()
    messages = _build_reporter_messages(state, verified_evidence, reference_numbers)
    if llm_client is None:
        if not config.api_key:
            raise ReporterFallbackError("LLM api_key is required")
        llm_client = get_llm_client(config, purpose="reporter", messages=messages)

    wire_api = get_llm_wire_api(llm_client)
    started = time.perf_counter()
```

Remove the duplicate `messages = _build_reporter_messages(...)` line that appears after client creation.

- [ ] **Step 5: Run call-site tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py::test_llm_analyst_creates_client_with_routing_context tests/test_agents.py::test_llm_reporter_creates_client_with_routing_context -v
```

Expected: both tests pass.

- [ ] **Step 6: Run full agent tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py -v
```

Expected: all agent tests pass.

- [ ] **Step 7: Commit call-site integration**

```powershell
git add src/insight_graph/agents/analyst.py src/insight_graph/agents/reporter.py tests/test_agents.py
git commit -m "feat: route analyst and reporter llm clients"
```

## Task 3: Documentation

**Files:**
- Modify: `docs/configuration.md`

- [ ] **Step 1: Add LLM router docs**

Add this section after the LLM Reporter configuration section in `docs/configuration.md`:

````markdown
## LLM Rules Router

InsightGraph can opt into an internal rules router that chooses among user-defined model tiers while keeping the same OpenAI-compatible endpoint configuration.

```bash
INSIGHT_GRAPH_LLM_ROUTER=rules \
INSIGHT_GRAPH_LLM_MODEL_FAST=gpt-4o-mini \
INSIGHT_GRAPH_LLM_MODEL_DEFAULT=gpt-4.1-mini \
INSIGHT_GRAPH_LLM_MODEL_STRONG=gpt-4.1 \
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_LLM_ROUTER` | 设置为 `rules` 时启用内部规则路由；未设置时使用 `INSIGHT_GRAPH_LLM_MODEL` | 未启用 |
| `INSIGHT_GRAPH_LLM_MODEL_FAST` | 短 default-purpose prompt 使用的低成本模型 | 回退到 default tier |
| `INSIGHT_GRAPH_LLM_MODEL_DEFAULT` | 默认模型 tier | `INSIGHT_GRAPH_LLM_MODEL` 或 `gpt-4o-mini` |
| `INSIGHT_GRAPH_LLM_MODEL_STRONG` | Reporter 或长 prompt 使用的强模型 | 回退到 default tier |
| `INSIGHT_GRAPH_LLM_ROUTER_FAST_CHAR_THRESHOLD` | default-purpose prompt 字符数小于等于该值时使用 fast tier | `2000` |
| `INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD` | prompt 字符数超过该值时使用 strong tier | `12000` |

Routing is deterministic and does not call a classifier model. Reporter uses the strong tier. Analyst uses the default tier unless the prompt exceeds the strong threshold. Default-purpose short prompts can use the fast tier.

LiteLLM Proxy can be used without adding a Python dependency by pointing `INSIGHT_GRAPH_LLM_BASE_URL` at the proxy and using proxy model aliases as tier names:

```bash
INSIGHT_GRAPH_LLM_BASE_URL=http://localhost:4000/v1 \
INSIGHT_GRAPH_LLM_API_KEY=proxy-key \
INSIGHT_GRAPH_LLM_ROUTER=rules \
INSIGHT_GRAPH_LLM_MODEL_FAST=cheap-model-alias \
INSIGHT_GRAPH_LLM_MODEL_DEFAULT=default-model-alias \
INSIGHT_GRAPH_LLM_MODEL_STRONG=strong-model-alias \
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm
```
````

If adding the section manually, ensure the fenced code blocks are correctly nested in Markdown by closing each bash block before continuing text.

- [ ] **Step 2: Run docs diff check**

Run:

```powershell
git diff --check -- docs/configuration.md
```

Expected: no output.

- [ ] **Step 3: Commit docs**

```powershell
git add docs/configuration.md
git commit -m "docs: document llm rules router"
```

## Task 4: Final Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_router.py tests/test_llm_client.py tests/test_llm_config.py tests/test_agents.py -v
```

Expected: all focused tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
```

Expected: full suite passes with the existing skipped test count.

- [ ] **Step 3: Run lint**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
```

Expected: `All checks passed!`.

- [ ] **Step 4: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no output.

- [ ] **Step 5: Inspect status and commits**

Run:

```powershell
git status --short --branch
git log --oneline --max-count=8
```

Expected: clean feature branch with implementation commits on top of the plan/spec commits.

## Self-Review Checklist

- Spec coverage: opt-in rules router, user-defined tiers, fallback chain, thresholds, no LiteLLM SDK dependency, LiteLLM Proxy compatibility, agent purpose/messages, observability through selected model, error handling, tests, and docs are covered.
- Unfinished marker scan: the plan contains no unresolved implementation sections.
- Type consistency: `get_llm_client(config=None, *, purpose="default", messages=None)` and `select_llm_model(config, *, purpose="default", messages=None)` are used consistently.
- Scope check: this is one focused subsystem and does not add public API changes, classifier routing, provider pricing, or per-user policy.
