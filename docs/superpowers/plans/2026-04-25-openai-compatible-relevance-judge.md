# OpenAI-Compatible Relevance Judge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in OpenAI-compatible LLM relevance judge that supports OpenAI official endpoints and compatible relay/model providers while keeping deterministic judge as the default.

**Architecture:** Add `openai` as a runtime dependency, extend `relevance.py` with OpenAI-compatible config resolution, client creation, JSON parsing, and fail-closed judging, and document the new env vars. Tests use fake clients only.

**Tech Stack:** Python 3.11+, Pydantic, OpenAI Python SDK, Pytest, Ruff.

---

## File Structure

- Modify: `pyproject.toml` - add `openai>=1.0.0` runtime dependency.
- Modify: `src/insight_graph/agents/relevance.py` - add `OpenAICompatibleRelevanceJudge`, config helpers, client factory, JSON parser, and judge resolution.
- Modify: `tests/test_relevance.py` - add fake OpenAI-compatible client tests.
- Modify: `README.md` - document `openai_compatible` relevance judge and env vars.

---

### Task 1: OpenAI Dependency And Judge Resolution Tests

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_relevance.py`

- [ ] **Step 1: Add failing resolution and config tests**

Modify import in `tests/test_relevance.py` from:

```python
from insight_graph.agents.relevance import (
    DeterministicRelevanceJudge,
    EvidenceRelevanceDecision,
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
    _resolve_openai_compatible_config,
    filter_relevant_evidence,
    get_relevance_judge,
    is_relevance_filter_enabled,
)
```

Append these tests to `tests/test_relevance.py`:

```python

def test_get_relevance_judge_accepts_openai_compatible() -> None:
    judge = get_relevance_judge("openai_compatible")

    assert isinstance(judge, OpenAICompatibleRelevanceJudge)


def test_openai_compatible_config_prefers_insight_graph_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "ig-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    config = _resolve_openai_compatible_config()

    assert config.api_key == "ig-key"
    assert config.base_url == "https://relay.example/v1"
    assert config.model == "relay-model"


def test_openai_compatible_config_falls_back_to_openai_env(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    config = _resolve_openai_compatible_config()

    assert config.api_key == "openai-key"
    assert config.base_url == "https://api.openai.com/v1"
    assert config.model == "gpt-4o-mini"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_relevance.py::test_get_relevance_judge_accepts_openai_compatible tests/test_relevance.py::test_openai_compatible_config_prefers_insight_graph_env tests/test_relevance.py::test_openai_compatible_config_falls_back_to_openai_env -v`

Expected: FAIL with `ImportError` for `OpenAICompatibleRelevanceJudge` or `_resolve_openai_compatible_config`.

- [ ] **Step 3: Add OpenAI dependency**

Modify `pyproject.toml` dependencies to include `openai>=1.0.0`:

```toml
dependencies = [
  "beautifulsoup4>=4.12.0",
  "duckduckgo-search>=6.0.0",
  "langgraph>=0.2.0",
  "langchain-core>=0.3.0",
  "openai>=1.0.0",
  "pydantic>=2.7.0",
  "typer>=0.12.0",
  "rich>=13.7.0",
]
```

- [ ] **Step 4: Implement config model and judge resolution skeleton**

Modify `src/insight_graph/agents/relevance.py` by adding imports:

```python
from collections.abc import Callable
from typing import Any, Protocol
```

Replace the existing `from typing import Protocol` import with the code above.

Add this model after `EvidenceRelevanceDecision`:

```python
class OpenAICompatibleConfig(BaseModel):
    api_key: str | None
    base_url: str | None
    model: str
```

Add this skeleton class after `DeterministicRelevanceJudge`:

```python
class OpenAICompatibleRelevanceJudge:
    def __init__(
        self,
        client: Any | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        client_factory: Callable[[str, str | None], Any] | None = None,
    ) -> None:
        config = _resolve_openai_compatible_config(api_key, base_url, model)
        self._client = client
        self._client_factory = client_factory or _create_openai_client
        self._api_key = config.api_key
        self._base_url = config.base_url
        self._model = config.model

    def judge(
        self,
        query: str,
        subtask: Subtask,
        evidence: Evidence,
    ) -> EvidenceRelevanceDecision:
        return EvidenceRelevanceDecision(
            evidence_id=evidence.id,
            relevant=False,
            reason="OpenAI-compatible relevance judge is not implemented yet.",
        )
```

Add these helpers before `is_relevance_filter_enabled`:

```python
def _resolve_openai_compatible_config(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> OpenAICompatibleConfig:
    return OpenAICompatibleConfig(
        api_key=api_key or os.getenv("INSIGHT_GRAPH_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=base_url or os.getenv("INSIGHT_GRAPH_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
        model=model or os.getenv("INSIGHT_GRAPH_LLM_MODEL", "gpt-4o-mini"),
    )


def _create_openai_client(api_key: str, base_url: str | None) -> Any:
    from openai import OpenAI

    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)
```

Modify `get_relevance_judge`:

```python
def get_relevance_judge(name: str | None = None) -> RelevanceJudge:
    judge_name = (name or os.getenv("INSIGHT_GRAPH_RELEVANCE_JUDGE", "deterministic")).lower()
    if judge_name == "deterministic":
        return DeterministicRelevanceJudge()
    if judge_name == "openai_compatible":
        return OpenAICompatibleRelevanceJudge()
    raise ValueError(f"Unknown relevance judge: {judge_name}")
```

- [ ] **Step 5: Run targeted tests**

Run: `python -m pytest tests/test_relevance.py::test_get_relevance_judge_accepts_openai_compatible tests/test_relevance.py::test_openai_compatible_config_prefers_insight_graph_env tests/test_relevance.py::test_openai_compatible_config_falls_back_to_openai_env -v`

Expected: selected tests pass.

- [ ] **Step 6: Run all relevance tests and lint**

Run: `python -m pytest tests/test_relevance.py -v`

Expected: all relevance tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/insight_graph/agents/relevance.py tests/test_relevance.py
git commit -m "feat: add openai compatible judge configuration"
```

---

### Task 2: OpenAI-Compatible Judge Decisions

**Files:**
- Modify: `src/insight_graph/agents/relevance.py`
- Modify: `tests/test_relevance.py`

- [ ] **Step 1: Add fake client tests**

Append to `tests/test_relevance.py`:

```python

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


def test_openai_compatible_judge_keeps_relevant_json_response() -> None:
    completions = FakeOpenAICompletions(
        '{"relevant": true, "reason": "Evidence directly matches the query."}'
    )
    judge = OpenAICompatibleRelevanceJudge(
        client=FakeOpenAIClient(completions),
        api_key="test-key",
        model="relay-model",
    )
    evidence = make_evidence(id="openai-kept")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="openai-kept",
        relevant=True,
        reason="Evidence directly matches the query.",
    )
    assert completions.calls[0]["model"] == "relay-model"
    assert completions.calls[0]["response_format"] == {"type": "json_object"}
    messages = completions.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Compare AI coding agents" in messages[1]["content"]
    assert "Cursor Pricing" in messages[1]["content"]


def test_openai_compatible_judge_filters_false_json_response() -> None:
    completions = FakeOpenAICompletions(
        '{"relevant": false, "reason": "Evidence is unrelated."}'
    )
    judge = OpenAICompatibleRelevanceJudge(
        client=FakeOpenAIClient(completions),
        api_key="test-key",
    )
    evidence = make_evidence(id="openai-filtered")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="openai-filtered",
        relevant=False,
        reason="Evidence is unrelated.",
    )


def test_openai_compatible_judge_fails_closed_for_missing_api_key() -> None:
    judge = OpenAICompatibleRelevanceJudge(api_key=None)
    evidence = make_evidence(id="missing-key")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="missing-key",
        relevant=False,
        reason="OpenAI-compatible relevance judge is missing an API key.",
    )


def test_openai_compatible_judge_fails_closed_for_api_error() -> None:
    completions = FakeOpenAICompletions(error=RuntimeError("relay unavailable"))
    judge = OpenAICompatibleRelevanceJudge(
        client=FakeOpenAIClient(completions),
        api_key="test-key",
    )
    evidence = make_evidence(id="api-error")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is False
    assert decision.reason == "OpenAI-compatible relevance judge failed: relay unavailable"


def test_openai_compatible_judge_fails_closed_for_invalid_json() -> None:
    completions = FakeOpenAICompletions("not json")
    judge = OpenAICompatibleRelevanceJudge(
        client=FakeOpenAIClient(completions),
        api_key="test-key",
    )
    evidence = make_evidence(id="invalid-json")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="invalid-json",
        relevant=False,
        reason="OpenAI-compatible relevance judge returned invalid JSON.",
    )


def test_openai_compatible_judge_fails_closed_for_invalid_schema() -> None:
    completions = FakeOpenAICompletions('{"reason": "Missing relevant field."}')
    judge = OpenAICompatibleRelevanceJudge(
        client=FakeOpenAIClient(completions),
        api_key="test-key",
    )
    evidence = make_evidence(id="invalid-schema")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="invalid-schema",
        relevant=False,
        reason="OpenAI-compatible relevance judge returned invalid JSON.",
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_relevance.py -v`

Expected: FAIL because `OpenAICompatibleRelevanceJudge.judge()` still returns the skeleton not-implemented decision.

- [ ] **Step 3: Implement judge decisions and parser**

Modify `src/insight_graph/agents/relevance.py`.

Add import:

```python
import json
```

Replace `OpenAICompatibleRelevanceJudge.judge` with:

```python
    def judge(
        self,
        query: str,
        subtask: Subtask,
        evidence: Evidence,
    ) -> EvidenceRelevanceDecision:
        if not self._api_key:
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="OpenAI-compatible relevance judge is missing an API key.",
            )
        try:
            client = self._client or self._client_factory(self._api_key, self._base_url)
            response = client.chat.completions.create(
                model=self._model,
                messages=_build_relevance_messages(query, subtask, evidence),
                response_format={"type": "json_object"},
                temperature=0,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("empty response")
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

Add helpers before `is_relevance_filter_enabled`:

```python
def _build_relevance_messages(
    query: str,
    subtask: Subtask,
    evidence: Evidence,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You judge whether one evidence item is relevant to a research subtask. "
                "Return only JSON with keys relevant (boolean) and reason (string)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Research query: {query}\n"
                f"Subtask id: {subtask.id}\n"
                f"Subtask description: {subtask.description}\n"
                f"Evidence id: {evidence.id}\n"
                f"Evidence title: {evidence.title}\n"
                f"Evidence source URL: {evidence.source_url}\n"
                f"Evidence verified: {evidence.verified}\n"
                f"Evidence snippet: {evidence.snippet}\n"
            ),
        },
    ]


def _parse_relevance_json(content: str, evidence_id: str) -> EvidenceRelevanceDecision:
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("response is not a JSON object")
    relevant = parsed.get("relevant")
    if not isinstance(relevant, bool):
        raise ValueError("relevant must be a boolean")
    reason = parsed.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = "OpenAI-compatible relevance judge returned a decision."
    return EvidenceRelevanceDecision(
        evidence_id=evidence_id,
        relevant=relevant,
        reason=reason,
    )
```

- [ ] **Step 4: Run relevance tests**

Run: `python -m pytest tests/test_relevance.py -v`

Expected: all relevance tests pass.

- [ ] **Step 5: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/agents/relevance.py tests/test_relevance.py
git commit -m "feat: add openai compatible relevance decisions"
```

---

### Task 3: Client Factory And Executor Integration Verification

**Files:**
- Modify: `tests/test_relevance.py`

- [ ] **Step 1: Add client factory and integration tests**

Append to `tests/test_relevance.py`:

```python

def test_openai_compatible_judge_uses_client_factory_with_base_url() -> None:
    completions = FakeOpenAICompletions(
        '{"relevant": true, "reason": "Factory client response."}'
    )
    calls = []

    def fake_client_factory(api_key: str, base_url: str | None):
        calls.append((api_key, base_url))
        return FakeOpenAIClient(completions)

    judge = OpenAICompatibleRelevanceJudge(
        api_key="factory-key",
        base_url="https://relay.example/v1",
        model="factory-model",
        client_factory=fake_client_factory,
    )
    evidence = make_evidence(id="factory")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is True
    assert calls == [("factory-key", "https://relay.example/v1")]


def test_filter_relevant_evidence_uses_openai_compatible_judge() -> None:
    completions = FakeOpenAICompletions(
        '{"relevant": false, "reason": "LLM filtered this evidence."}'
    )
    judge = OpenAICompatibleRelevanceJudge(
        client=FakeOpenAIClient(completions),
        api_key="test-key",
    )
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = [make_evidence(id="llm-filtered")]

    kept, filtered_count = filter_relevant_evidence(
        "Compare AI coding agents",
        subtask,
        evidence,
        judge=judge,
    )

    assert kept == []
    assert filtered_count == 1
```

- [ ] **Step 2: Run new tests**

Run: `python -m pytest tests/test_relevance.py::test_openai_compatible_judge_uses_client_factory_with_base_url tests/test_relevance.py::test_filter_relevant_evidence_uses_openai_compatible_judge -v`

Expected: selected tests pass.

- [ ] **Step 3: Run executor integration tests under OpenAI-compatible env**

Run: `$env:INSIGHT_GRAPH_RELEVANCE_FILTER='1'; $env:INSIGHT_GRAPH_RELEVANCE_JUDGE='deterministic'; python -m pytest tests/test_executor.py -v`

Expected: executor tests pass using deterministic judge.

Run: `python -m pytest tests/test_relevance.py tests/test_executor.py -v`

Expected: all selected tests pass without live network access.

- [ ] **Step 4: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 5: Commit**

```bash
git add tests/test_relevance.py
git commit -m "test: cover openai compatible relevance integration"
```

---

### Task 4: Documentation And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README relevance section**

In `README.md`, replace:

```markdown
| `INSIGHT_GRAPH_RELEVANCE_JUDGE` | 当前仅支持 `deterministic` | `deterministic` |
```

with:

```markdown
| `INSIGHT_GRAPH_RELEVANCE_JUDGE` | `deterministic` 或 `openai_compatible` | `deterministic` |
| `INSIGHT_GRAPH_LLM_API_KEY` | OpenAI-compatible provider API key；缺省时 fallback 到 `OPENAI_API_KEY` | - |
| `INSIGHT_GRAPH_LLM_BASE_URL` | OpenAI-compatible `/v1` endpoint；缺省时 fallback 到 `OPENAI_BASE_URL` | - |
| `INSIGHT_GRAPH_LLM_MODEL` | OpenAI-compatible relevance model | `gpt-4o-mini` |
```

Replace:

```markdown
当前 relevance judge 不调用真实 LLM，只进行 deterministic/offline 过滤：未 verified 或缺少 title/source URL/snippet 的 evidence 会被丢弃。真实 Qwen/OpenAI relevance judge 属于后续阶段。
```

with:

```markdown
默认 relevance judge 不调用真实 LLM，只进行 deterministic/offline 过滤：未 verified 或缺少 title/source URL/snippet 的 evidence 会被丢弃。需要真实 LLM 判断时，可设置 `INSIGHT_GRAPH_RELEVANCE_JUDGE=openai_compatible`，并配置 OpenAI 官方或兼容中转的 API key、base URL 和模型名。测试默认不调用外部 LLM。
```

Add this example below the paragraph:

```markdown

OpenAI-compatible 中转示例：

```bash
INSIGHT_GRAPH_RELEVANCE_FILTER=1 INSIGHT_GRAPH_RELEVANCE_JUDGE=openai_compatible INSIGHT_GRAPH_LLM_API_KEY=sk-... INSIGHT_GRAPH_LLM_BASE_URL=https://relay.example/v1 INSIGHT_GRAPH_LLM_MODEL=gpt-4o-mini python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```
```

- [ ] **Step 2: Run final verification**

Run: `python -m pytest -v`

Expected: all tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

Run: `python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"`

Expected: output includes `# InsightGraph Research Report`, `## Key Findings`, and `## References`. Do not set OpenAI-compatible env vars for this smoke test.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document openai compatible relevance judge"
```

---

## Self-Review

- Spec coverage: The plan implements the OpenAI dependency, OpenAI-compatible judge resolution, config fallback, custom base URL support, fake-client decision tests, fail-closed missing key/API/JSON behavior, README documentation, and default offline verification.
- Deferred scope: Native Anthropic/Gemini/DashScope SDKs, LLM router, streaming, batch relevance, token budgets, and full prompt/response logging remain excluded.
- Placeholder scan: No placeholders remain; each task includes exact file paths, code, commands, expected failures, expected pass conditions, and commit commands.
- Type consistency: `OpenAICompatibleRelevanceJudge`, `OpenAICompatibleConfig`, `_resolve_openai_compatible_config`, `_create_openai_client`, `_parse_relevance_json`, and `openai_compatible` are consistently named across tasks.
