# Relevance Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in deterministic relevance filtering to Executor evidence flow while preserving default offline behavior.

**Architecture:** Extend `ToolCallRecord` with `filtered_count`, add a focused `relevance.py` module for deterministic judge and filter helpers, then integrate filtering into Executor behind `INSIGHT_GRAPH_RELEVANCE_FILTER`.

**Tech Stack:** Python 3.11+, Pydantic, Pytest, Ruff.

---

## File Structure

- Modify: `src/insight_graph/state.py` - add `filtered_count` to `ToolCallRecord`.
- Modify: `tests/test_state.py` - assert `filtered_count` default.
- Create: `src/insight_graph/agents/relevance.py` - relevance decision model, judge protocol, deterministic judge, env helpers, filter helper.
- Create: `tests/test_relevance.py` - relevance judge, env parsing, provider resolution, filter helper tests.
- Modify: `src/insight_graph/agents/executor.py` - apply optional filtering per tool result group and record filtered counts.
- Modify: `tests/test_executor.py` - cover disabled default, enabled filtering, filtered count.
- Modify: `README.md` - document opt-in deterministic relevance filtering.

---

### Task 1: Tool Call Filtered Count

**Files:**
- Modify: `src/insight_graph/state.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Write failing state test**

Modify `test_tool_call_record_defaults_to_success` in `tests/test_state.py` to include:

```python
    assert record.filtered_count == 0
```

Full expected test body:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py::test_tool_call_record_defaults_to_success -v`

Expected: FAIL with `AttributeError` for missing `filtered_count`.

- [ ] **Step 3: Implement filtered_count field**

Modify `ToolCallRecord` in `src/insight_graph/state.py`:

```python
class ToolCallRecord(BaseModel):
    subtask_id: str
    tool_name: str
    query: str
    evidence_count: int = 0
    filtered_count: int = 0
    success: bool = True
    error: str | None = None
```

- [ ] **Step 4: Run state tests**

Run: `python -m pytest tests/test_state.py -v`

Expected: all state tests pass.

- [ ] **Step 5: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/state.py tests/test_state.py
git commit -m "feat: track filtered evidence count"
```

---

### Task 2: Deterministic Relevance Judge

**Files:**
- Create: `src/insight_graph/agents/relevance.py`
- Create: `tests/test_relevance.py`

- [ ] **Step 1: Write failing relevance tests**

Create `tests/test_relevance.py`:

```python
import pytest

from insight_graph.agents.relevance import (
    DeterministicRelevanceJudge,
    EvidenceRelevanceDecision,
    filter_relevant_evidence,
    get_relevance_judge,
    is_relevance_filter_enabled,
)
from insight_graph.state import Evidence, Subtask


def make_evidence(**overrides) -> Evidence:
    data = {
        "id": "e1",
        "subtask_id": "collect",
        "title": "Cursor Pricing",
        "source_url": "https://cursor.com/pricing",
        "snippet": "Cursor pricing page.",
        "verified": True,
    }
    data.update(overrides)
    return Evidence(**data)


def test_deterministic_judge_keeps_complete_verified_evidence() -> None:
    judge = DeterministicRelevanceJudge()
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = make_evidence()

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="e1",
        relevant=True,
        reason="Evidence is verified and has required content.",
    )


def test_deterministic_judge_rejects_unverified_evidence() -> None:
    judge = DeterministicRelevanceJudge()
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = make_evidence(verified=False)

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is False
    assert decision.reason == "Evidence is not verified."


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("title", "Evidence title is empty."),
        ("source_url", "Evidence source URL is empty."),
        ("snippet", "Evidence snippet is empty."),
    ],
)
def test_deterministic_judge_rejects_empty_required_content(field: str, reason: str) -> None:
    judge = DeterministicRelevanceJudge()
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = make_evidence(**{field: "   "})

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is False
    assert decision.reason == reason


def test_get_relevance_judge_defaults_to_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_RELEVANCE_JUDGE", raising=False)

    assert isinstance(get_relevance_judge(), DeterministicRelevanceJudge)


def test_get_relevance_judge_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown relevance judge"):
        get_relevance_judge("unknown")


@pytest.mark.parametrize("value", ["1", "true", "yes", "TRUE"])
def test_relevance_filter_enabled_for_truthy_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", value)

    assert is_relevance_filter_enabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no"])
def test_relevance_filter_disabled_for_other_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", value)

    assert is_relevance_filter_enabled() is False


def test_filter_relevant_evidence_returns_kept_items_and_filtered_count() -> None:
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = [
        make_evidence(id="kept"),
        make_evidence(id="filtered", verified=False),
    ]

    kept, filtered_count = filter_relevant_evidence(
        "Compare AI coding agents",
        subtask,
        evidence,
        judge=DeterministicRelevanceJudge(),
    )

    assert [item.id for item in kept] == ["kept"]
    assert filtered_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_relevance.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.agents.relevance'`.

- [ ] **Step 3: Implement relevance module**

Create `src/insight_graph/agents/relevance.py`:

```python
import os
from typing import Protocol

from pydantic import BaseModel

from insight_graph.state import Evidence, Subtask


class EvidenceRelevanceDecision(BaseModel):
    evidence_id: str
    relevant: bool
    reason: str


class RelevanceJudge(Protocol):
    def judge(
        self,
        query: str,
        subtask: Subtask,
        evidence: Evidence,
    ) -> EvidenceRelevanceDecision: ...


class DeterministicRelevanceJudge:
    def judge(
        self,
        query: str,
        subtask: Subtask,
        evidence: Evidence,
    ) -> EvidenceRelevanceDecision:
        if not evidence.verified:
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="Evidence is not verified.",
            )
        if not evidence.title.strip():
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="Evidence title is empty.",
            )
        if not evidence.source_url.strip():
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="Evidence source URL is empty.",
            )
        if not evidence.snippet.strip():
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="Evidence snippet is empty.",
            )
        return EvidenceRelevanceDecision(
            evidence_id=evidence.id,
            relevant=True,
            reason="Evidence is verified and has required content.",
        )


def is_relevance_filter_enabled() -> bool:
    value = os.getenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "").lower()
    return value in {"1", "true", "yes"}


def get_relevance_judge(name: str | None = None) -> RelevanceJudge:
    judge_name = (name or os.getenv("INSIGHT_GRAPH_RELEVANCE_JUDGE", "deterministic")).lower()
    if judge_name == "deterministic":
        return DeterministicRelevanceJudge()
    raise ValueError(f"Unknown relevance judge: {judge_name}")


def filter_relevant_evidence(
    query: str,
    subtask: Subtask,
    evidence: list[Evidence],
    judge: RelevanceJudge | None = None,
) -> tuple[list[Evidence], int]:
    active_judge = judge or get_relevance_judge()
    kept: list[Evidence] = []
    filtered_count = 0
    for item in evidence:
        decision = active_judge.judge(query, subtask, item)
        if decision.relevant:
            kept.append(item)
        else:
            filtered_count += 1
    return kept, filtered_count
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
git commit -m "feat: add deterministic relevance judge"
```

---

### Task 3: Executor Relevance Filtering Integration

**Files:**
- Modify: `src/insight_graph/agents/executor.py`
- Modify: `tests/test_executor.py`

- [ ] **Step 1: Add failing executor filtering tests**

Append to `tests/test_executor.py`:

```python

def test_executor_does_not_filter_when_relevance_filter_disabled(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.delenv("INSIGHT_GRAPH_RELEVANCE_FILTER", raising=False)

    unverified = Evidence(
        id="unverified",
        subtask_id="collect",
        title="Unverified",
        source_url="https://example.com/unverified",
        snippet="Unverified evidence.",
        verified=False,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [unverified]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["unverified"]
    assert updated.tool_call_log[0].filtered_count == 0


def test_executor_filters_unverified_evidence_when_enabled(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "1")

    verified = Evidence(
        id="verified",
        subtask_id="collect",
        title="Verified",
        source_url="https://example.com/verified",
        snippet="Verified evidence.",
        verified=True,
    )
    unverified = Evidence(
        id="unverified",
        subtask_id="collect",
        title="Unverified",
        source_url="https://example.com/unverified",
        snippet="Unverified evidence.",
        verified=False,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [verified, unverified]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["verified"]
    assert updated.global_evidence_pool == updated.evidence_pool
    assert updated.tool_call_log[0].evidence_count == 2
    assert updated.tool_call_log[0].filtered_count == 1


def test_executor_filters_after_per_tool_deduplication(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "1")

    duplicate_unverified = Evidence(
        id="duplicate",
        subtask_id="collect",
        title="Duplicate",
        source_url="https://example.com/duplicate",
        snippet="Duplicate evidence.",
        verified=False,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [duplicate_unverified, duplicate_unverified.model_copy()]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert updated.evidence_pool == []
    assert updated.tool_call_log[0].evidence_count == 2
    assert updated.tool_call_log[0].filtered_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_executor.py -v`

Expected: FAIL because Executor does not apply relevance filtering and/or `filtered_count` remains `0`.

- [ ] **Step 3: Integrate filtering into Executor**

Replace `src/insight_graph/agents/executor.py` with:

```python
from insight_graph.agents.relevance import (
    filter_relevant_evidence,
    is_relevance_filter_enabled,
)
from insight_graph.state import Evidence, GraphState, ToolCallRecord
from insight_graph.tools import ToolRegistry


def execute_subtasks(state: GraphState) -> GraphState:
    registry = ToolRegistry()
    collected: list[Evidence] = []
    records = [ToolCallRecord.model_validate(record) for record in state.tool_call_log]
    filter_enabled = is_relevance_filter_enabled()

    for subtask in state.subtasks:
        for tool_name in subtask.suggested_tools:
            try:
                results = registry.run(tool_name, state.user_request, subtask.id)
            except Exception as exc:
                records.append(
                    ToolCallRecord(
                        subtask_id=subtask.id,
                        tool_name=tool_name,
                        query=state.user_request,
                        success=False,
                        error=str(exc),
                    )
                )
                continue

            deduped_results = _deduplicate_evidence(results)
            filtered_count = 0
            if filter_enabled:
                kept_results, filtered_count = filter_relevant_evidence(
                    state.user_request,
                    subtask,
                    deduped_results,
                )
            else:
                kept_results = deduped_results

            collected.extend(kept_results)
            records.append(
                ToolCallRecord(
                    subtask_id=subtask.id,
                    tool_name=tool_name,
                    query=state.user_request,
                    evidence_count=len(results),
                    filtered_count=filtered_count,
                )
            )

    deduped = _deduplicate_evidence(collected)
    state.evidence_pool = deduped
    state.global_evidence_pool = deduped
    state.tool_call_log = records
    return state


def _deduplicate_evidence(evidence: list[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str]] = set()
    deduped: list[Evidence] = []
    for item in evidence:
        key = (item.id, item.source_url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
```

- [ ] **Step 4: Run executor tests**

Run: `python -m pytest tests/test_executor.py -v`

Expected: all executor tests pass.

- [ ] **Step 5: Run broader tests**

Run: `python -m pytest tests/test_executor.py tests/test_relevance.py tests/test_agents.py tests/test_graph.py tests/test_cli.py -v`

Expected: all selected tests pass.

- [ ] **Step 6: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 7: Commit**

```bash
git add src/insight_graph/agents/executor.py tests/test_executor.py
git commit -m "feat: filter executor evidence by relevance"
```

---

### Task 4: Documentation And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README Search Provider section**

In `README.md`, after the Executor note that starts with `当前 Executor 是第一阶段实现`, add:

```markdown

Relevance filtering 默认关闭。需要过滤工具返回的 evidence 时，可显式启用 deterministic/offline judge：

```bash
INSIGHT_GRAPH_RELEVANCE_FILTER=1 python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_RELEVANCE_FILTER` | `1` / `true` / `yes` 时启用 Executor evidence relevance filtering | 未启用 |
| `INSIGHT_GRAPH_RELEVANCE_JUDGE` | 当前仅支持 `deterministic` | `deterministic` |

当前 relevance judge 不调用真实 LLM，只进行 deterministic/offline 过滤：未 verified 或缺少 title/source URL/snippet 的 evidence 会被丢弃。真实 Qwen/OpenAI relevance judge 属于后续阶段。
```

- [ ] **Step 2: Run final verification**

Run: `python -m pytest -v`

Expected: all tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

Run: `python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"`

Expected: output includes `# InsightGraph Research Report`, `## Key Findings`, and `## References`. Do not set relevance env vars for this smoke test.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document relevance filtering"
```

---

## Self-Review

- Spec coverage: The plan implements `filtered_count`, deterministic relevance decision/judge/filter helpers, env parsing, Executor integration behind `INSIGHT_GRAPH_RELEVANCE_FILTER`, per-tool filtered counts, README documentation, and default CLI verification.
- Deferred scope: Qwen/OpenAI judges, prompts, API keys, async/batch relevance, separate relevance logs, Reporter changes, and default behavior changes remain excluded.
- Placeholder scan: No placeholders remain; each task includes exact file paths, code, commands, expected failures, expected pass conditions, and commit commands.
- Type consistency: `EvidenceRelevanceDecision`, `RelevanceJudge`, `DeterministicRelevanceJudge`, `filter_relevant_evidence`, `is_relevance_filter_enabled`, `get_relevance_judge`, and `ToolCallRecord.filtered_count` are consistently named across tasks.
