# Reference Quality Deep Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring InsightGraph's report-generation quality close to the reference `wenyi-research-agent` README by adding deeper multi-round evidence collection, stricter budgets, long-document retrieval upgrades, checkpoint/memory infrastructure, and stronger observability without weakening deterministic offline defaults.

**Architecture:** Execute this as staged, independently verifiable phases. Phase 11 improves research depth without new heavy services; Phase 12 adds budgets and compression; Phase 13 adds semantic long-document retrieval; Phase 14 adds PostgreSQL checkpoint resume; Phase 15 adds pgvector long-term memory. Each phase must keep default CLI/tests offline and make live/network/LLM behavior opt-in.

**Tech Stack:** Python 3.11+, LangGraph, Pydantic, FastAPI, Typer, pytest, ruff; later phases may add PostgreSQL/SQLAlchemy/asyncpg and pgvector only after their phase spec is approved.

---

## Reference Quality Gap Summary

The reference README promises these production-grade research properties:

- Multi-round tool execution per subtask with convergence detection.
- Critic-driven replan that avoids repeated failed strategies.
- Token, step, and tool-call budgets.
- Conversation compression for long-running live investigations.
- TOC/page-aware and vector-assisted RAG for long PDFs and filings.
- PostgreSQL checkpoint resume.
- pgvector long-term memory.
- Full LLM observability with token accounting.
- Optional code execution and MCP-style tool extensibility.

InsightGraph already has the core report-quality foundation: Planner/Collector/Analyst/Critic/Reporter, domain profiles, entity resolution, section plans, section-aware queries, evidence scoring, citation support metadata, SEC filings/financials evidence, remote PDF/HTML chunks, rendered fetch, Eval Bench metrics, and quality gates.

The remaining quality gap is not basic citation safety. The largest gap is research depth: the system needs deeper evidence acquisition before analysis, explicit stop reasons, and bounded long-run behavior.

---

## File Structure

Immediate Phase 11 files:

- Modify `src/insight_graph/state.py`: add additive collection-depth metadata fields to `ToolCallRecord` and `GraphState`.
- Modify `src/insight_graph/agents/executor.py`: add multi-round section collection and stop-reason logic while preserving current single-round default.
- Modify `src/insight_graph/cli.py`: make `live-research` opt into deeper collection rounds.
- Modify `src/insight_graph/eval.py`: expose collection-depth metrics in Eval Bench summaries.
- Modify `tests/test_executor.py`: TDD coverage for multi-round collection, no-new-evidence stop, and max-round stop.
- Modify `tests/test_cli.py`: TDD coverage for `live-research` defaults.
- Modify `tests/test_eval.py`: TDD coverage for new collection-depth metrics.
- Modify `README.md`, `docs/configuration.md`, and `docs/report-quality-roadmap.md`: document the new reference-quality phase and current boundaries.
- Modify `CHANGELOG.md`: record each phase under Unreleased.

Later phase files after separate specs:

- Create `src/insight_graph/report_quality/budgeting.py`: central budget parsing and enforcement helpers.
- Create `src/insight_graph/report_quality/conversation_compression.py`: evidence-preserving compression summaries.
- Create `src/insight_graph/report_quality/document_index.py`: deterministic and later vector-backed chunk indexing.
- Create `src/insight_graph/persistence/`: PostgreSQL checkpoint storage and migration logic.
- Create `src/insight_graph/memory/`: pgvector memory write/read interfaces.

---

## Milestone Order

1. Phase 11: Research Depth v1. Add bounded multi-round evidence collection per section, stop reasons, and eval metrics. No new service dependencies.
2. Phase 12: Budgets and compression. Add global token/step/tool/fetch budgets and evidence-preserving conversation compression. No database dependency.
3. Phase 13: Long-document retrieval v3. Add semantic-ready document indexing and optional vector retrieval behind explicit opt-in.
4. Phase 14: PostgreSQL checkpoint resume. Add durable workflow resume with migration tests.
5. Phase 15: pgvector memory. Add opt-in embeddings, privacy/deletion controls, and eval proof that memory improves grounded reports.
6. Phase 16: Production observability and extensibility. Add opt-in full LLM trace export, MCP-style external tool registry, and sandboxed code execution only if explicitly approved.

Each milestone must finish with full `pytest`, full `ruff`, `git diff --check`, commit, merge to `master`, and worktree cleanup.

---

## Phase 11: Research Depth v1

### Task 1: Add Collection Depth Metadata

**Files:**
- Modify: `src/insight_graph/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing test**

Add this test to `tests/test_state.py`:

```python
from insight_graph.state import GraphState, ToolCallRecord


def test_collection_depth_metadata_defaults_are_backward_compatible() -> None:
    record = ToolCallRecord(subtask_id="collect", tool_name="mock_search", query="q")
    state = GraphState(user_request="q")

    assert record.round_index == 1
    assert record.section_id is None
    assert record.stop_reason is None
    assert state.collection_rounds == []
    assert state.collection_stop_reason is None
```

- [ ] **Step 2: Run the RED test**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_state.py::test_collection_depth_metadata_defaults_are_backward_compatible -v
```

Expected: FAIL because `round_index`, `section_id`, `stop_reason`, `collection_rounds`, and `collection_stop_reason` do not exist.

- [ ] **Step 3: Implement minimal additive fields**

Update `src/insight_graph/state.py`:

```python
class ToolCallRecord(BaseModel):
    subtask_id: str
    tool_name: str
    query: str
    evidence_count: int = 0
    filtered_count: int = 0
    success: bool = True
    error: str | None = None
    round_index: int = 1
    section_id: str | None = None
    stop_reason: str | None = None


class GraphState(BaseModel):
    user_request: str
    domain_profile: str | None = None
    resolved_entities: list[dict[str, object]] = Field(default_factory=list)
    section_research_plan: list[dict[str, object]] = Field(default_factory=list)
    section_collection_status: list[dict[str, object]] = Field(default_factory=list)
    evidence_scores: list[dict[str, object]] = Field(default_factory=list)
    citation_support: list[dict[str, object]] = Field(default_factory=list)
    replan_requests: list[dict[str, object]] = Field(default_factory=list)
    subtasks: list[Subtask] = Field(default_factory=list)
    evidence_pool: list[Evidence] = Field(default_factory=list)
    global_evidence_pool: list[Evidence] = Field(default_factory=list)
    tool_call_log: list[ToolCallRecord] = Field(default_factory=list)
    llm_call_log: list[LLMCallRecord] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    competitive_matrix: list[CompetitiveMatrixRow] = Field(default_factory=list)
    critique: Critique | None = None
    report_markdown: str | None = None
    iterations: int = 0
    collection_rounds: list[dict[str, object]] = Field(default_factory=list)
    collection_stop_reason: str | None = None
```

- [ ] **Step 4: Run the GREEN test**

Run the same test command. Expected: PASS.

- [ ] **Step 5: Run targeted state tests**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_state.py -v
```

Expected: PASS.

### Task 2: Add Runtime Collection Depth Config

**Files:**
- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_executor.py`:

```python
def test_max_collection_rounds_defaults_to_one(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.delenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", raising=False)

    assert executor_module._max_collection_rounds() == 1


def test_max_collection_rounds_reads_positive_integer(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", "3")

    assert executor_module._max_collection_rounds() == 3


def test_max_collection_rounds_ignores_invalid_values(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", "0")

    assert executor_module._max_collection_rounds() == 1
```

- [ ] **Step 2: Run RED tests**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_executor.py::test_max_collection_rounds_defaults_to_one tests/test_executor.py::test_max_collection_rounds_reads_positive_integer tests/test_executor.py::test_max_collection_rounds_ignores_invalid_values -v
```

Expected: FAIL because `_max_collection_rounds` does not exist.

- [ ] **Step 3: Implement config helper**

Add to `src/insight_graph/agents/executor.py`:

```python
import os

MAX_COLLECTION_ROUNDS_ENV = "INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS"


def _max_collection_rounds() -> int:
    raw_value = os.environ.get(MAX_COLLECTION_ROUNDS_ENV, "1")
    try:
        value = int(raw_value)
    except ValueError:
        return 1
    return value if value > 0 else 1
```

- [ ] **Step 4: Run GREEN tests**

Run the same test command. Expected: PASS.

### Task 3: Execute Multiple Section Collection Rounds

**Files:**
- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write failing multi-round test**

Add this test:

```python
def test_executor_runs_additional_round_for_insufficient_section(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", "2")
    observed_queries: list[str] = []

    official = Evidence(
        id="official",
        subtask_id="collect",
        title="Official Evidence",
        source_url="https://example.com/official",
        snippet="Official evidence has enough words for relevance.",
        source_type="official_site",
        verified=True,
    )
    news = Evidence(
        id="news",
        subtask_id="collect",
        title="News Evidence",
        source_url="https://example.com/news",
        snippet="News evidence has enough words for relevance.",
        source_type="news",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            observed_queries.append(query)
            if len(observed_queries) == 1:
                return [official]
            return [news]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="Compare AI coding agents",
        section_research_plan=[
            {
                "section_id": "market-signals",
                "title": "Market Signals",
                "questions": ["What market news exists?"],
                "required_source_types": ["official_site", "news"],
                "min_evidence": 2,
                "budget": 3,
            }
        ],
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [record.round_index for record in updated.tool_call_log] == [1, 2]
    assert "missing source types: news" in observed_queries[1]
    assert {item.id for item in updated.evidence_pool} == {"official", "news"}
    assert updated.section_collection_status[0]["sufficient"] is True
    assert updated.collection_stop_reason == "sufficient"
```

- [ ] **Step 2: Run RED test**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_executor.py::test_executor_runs_additional_round_for_insufficient_section -v
```

Expected: FAIL because Executor only runs one collection round.

- [ ] **Step 3: Implement round loop**

Refactor `execute_subtasks()` so it:

```python
def execute_subtasks(state: GraphState) -> GraphState:
    registry = ToolRegistry()
    collected: list[Evidence] = _existing_retry_evidence(state)
    records = [ToolCallRecord.model_validate(record) for record in state.tool_call_log]
    filter_enabled = is_relevance_filter_enabled()
    max_rounds = _max_collection_rounds()
    previous_evidence_keys: set[tuple[str, str]] = set()
    round_summaries: list[dict[str, object]] = []
    stop_reason = "max_rounds"

    for round_index in range(1, max_rounds + 1):
        before_count = len(_deduplicate_evidence(collected))
        section_focus = _section_focus_for_round(state, collected, round_index)
        for subtask in state.subtasks:
            for tool_name in subtask.suggested_tools:
                query = _collection_query(state, tool_name, section_focus)
                kept_results, new_records = _run_tool_with_fallback(
                    registry,
                    tool_name,
                    query,
                    subtask,
                    filter_enabled,
                    state.llm_call_log,
                    round_index=round_index,
                    section_id=section_focus.get("section_id") if section_focus else None,
                )
                collected.extend(kept_results)
                records.extend(new_records)

        state = _finalize_collected_evidence(state, collected, records)
        after_keys = {(item.id, item.source_url) for item in state.evidence_pool}
        new_count = len(after_keys - previous_evidence_keys)
        previous_evidence_keys = after_keys
        round_summaries.append(
            {
                "round": round_index,
                "new_evidence_count": max(0, len(state.evidence_pool) - before_count),
                "total_evidence_count": len(state.evidence_pool),
                "sufficient": _all_sections_sufficient(state.section_collection_status),
            }
        )
        if _all_sections_sufficient(state.section_collection_status):
            stop_reason = "sufficient"
            break
        if round_index > 1 and new_count == 0:
            stop_reason = "no_new_evidence"
            break

    state.collection_rounds = round_summaries
    state.collection_stop_reason = stop_reason
    return state
```

Create `_finalize_collected_evidence()`, `_all_sections_sufficient()`, and `_section_focus_for_round()` in the same file. `_section_focus_for_round()` must return `None` for round 1 and the first insufficient section status for later rounds.

Update `_collection_query()` signature to accept `section_focus: dict[str, object] | None = None` and append `section`, `missing source types`, and `missing evidence` from the focus before replan hints.

- [ ] **Step 4: Update `_run_tool_with_fallback()` metadata**

Add keyword-only args:

```python
round_index: int = 1,
section_id: str | None = None,
```

Set those fields on every `ToolCallRecord`, including mock fallback records.

- [ ] **Step 5: Run GREEN test**

Run the same test. Expected: PASS.

### Task 4: Stop on No New Evidence

**Files:**
- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write failing test**

```python
def test_executor_stops_when_follow_up_adds_no_new_evidence(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", "3")
    duplicate = Evidence(
        id="official",
        subtask_id="collect",
        title="Official Evidence",
        source_url="https://example.com/official",
        snippet="Official evidence has enough words for relevance.",
        source_type="official_site",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [duplicate]

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        section_research_plan=[
            {
                "section_id": "market-signals",
                "required_source_types": ["official_site", "news"],
                "min_evidence": 2,
                "budget": 3,
            }
        ],
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert [record.round_index for record in updated.tool_call_log] == [1, 2]
    assert updated.collection_stop_reason == "no_new_evidence"
```

- [ ] **Step 2: Run RED test**

Expected: FAIL until no-new-evidence stop is correct.

- [ ] **Step 3: Fix stop logic**

Compare each round's deduped `(id, source_url)` set to the prior round's set after assignment/scoring/capping. If round index is greater than 1 and the set does not grow, stop with `collection_stop_reason = "no_new_evidence"`.

- [ ] **Step 4: Run GREEN test**

Expected: PASS.

### Task 5: Live Research Preset Enables Deeper Collection

**Files:**
- Modify: `src/insight_graph/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py` near existing preset tests:

```python
def test_live_research_preset_sets_collection_rounds(monkeypatch) -> None:
    from insight_graph.cli import ResearchPreset, _apply_research_preset

    monkeypatch.delenv("INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS", raising=False)

    _apply_research_preset(ResearchPreset.live_research)

    assert os.environ["INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS"] == "3"
```

- [ ] **Step 2: Run RED test**

Expected: FAIL because preset does not set the variable.

- [ ] **Step 3: Implement preset default**

Add to `LIVE_RESEARCH_PRESET_DEFAULTS`:

```python
"INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS": "3",
```

- [ ] **Step 4: Run GREEN test**

Expected: PASS.

### Task 6: Eval Reports Collection Depth

**Files:**
- Modify: `src/insight_graph/eval.py`
- Test: `tests/test_eval.py`

- [ ] **Step 1: Write failing test**

Add a test that builds a `GraphState` with `collection_rounds=[{"round": 1}, {"round": 2}]` and `collection_stop_reason="sufficient"`, then asserts case quality includes `collection_round_count` and `collection_stop_reason`, and summary includes `average_collection_round_count`.

- [ ] **Step 2: Run RED test**

Expected: FAIL because Eval Bench does not expose collection-depth metrics.

- [ ] **Step 3: Implement metrics**

Add to case result or quality payload:

```python
"collection_round_count": len(state.collection_rounds),
"collection_stop_reason": state.collection_stop_reason or "unknown",
```

Add summary aggregate:

```python
"average_collection_round_count": round(
    sum(int(item.get("quality", {}).get("collection_round_count", 0)) for item in case_results)
    / len(case_results)
) if case_results else 0,
```

Add Markdown output columns only if this does not make tables unwieldy; otherwise put it in the summary table.

- [ ] **Step 4: Run GREEN test**

Expected: PASS.

### Task 7: Phase 11 Verification and Commit


- [ ] **Step 1: Run targeted tests**

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_state.py tests/test_executor.py tests/test_cli.py tests/test_eval.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full verification**

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: `pytest` all pass, ruff reports `All checks passed!`, and `git diff --check` has no output.

- [ ] **Step 3: Commit**

```powershell
git add src/insight_graph/state.py src/insight_graph/agents/executor.py src/insight_graph/cli.py src/insight_graph/eval.py tests/test_state.py tests/test_executor.py tests/test_cli.py tests/test_eval.py README.md docs/configuration.md docs/report-quality-roadmap.md CHANGELOG.md
git commit -m "feat(research): add multi-round collection depth"
```

---

## Phase 12: Budgets and Compression

### Task 1: Central Budget Config

**Files:**
- Create: `src/insight_graph/report_quality/budgeting.py`
- Test: `tests/test_budgeting.py`

Required behavior:

- Parse `INSIGHT_GRAPH_MAX_TOOL_CALLS`, default `20`.
- Parse `INSIGHT_GRAPH_MAX_STEPS`, default `10`.
- Parse `INSIGHT_GRAPH_MAX_FETCHES`, default `10`.
- Parse `INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN`, default current `20`.
- Invalid, zero, or negative values fall back to defaults.

Acceptance command:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_budgeting.py -v
```

### Task 2: Enforce Tool-Call Budget

**Files:**
- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_executor.py`

Required behavior:

- Stop collection before a tool call that would exceed `INSIGHT_GRAPH_MAX_TOOL_CALLS`.
- Set `collection_stop_reason = "tool_budget_exhausted"`.
- Add a final failed `ToolCallRecord` only if a specific skipped call is useful to users; otherwise record the stop reason in `collection_rounds`.

### Task 3: Evidence-Preserving Conversation Compression

**Files:**
- Create: `src/insight_graph/report_quality/conversation_compression.py`
- Modify: `src/insight_graph/state.py`
- Test: `tests/test_conversation_compression.py`

Required behavior:

- Summarize old tool/LLM metadata without dropping `Evidence.id`, `source_url`, `section_id`, `verified`, or citation support references.
- Trigger only when `INSIGHT_GRAPH_MAX_CONVERSATION_CHARS` is set and exceeded.
- Default path must remain unchanged.

---

## Phase 13: Long-Document Retrieval v3

### Task 1: Deterministic Document Index Contract

**Files:**
- Create: `src/insight_graph/report_quality/document_index.py`
- Test: `tests/test_document_index.py`

Required behavior:

- Represent chunks with `chunk_id`, `source_url`, `chunk_index`, `document_page`, `section_heading`, `text`, and `tokens`.
- Rank chunks by exact term, heading match, page/TOC metadata, and source authority.
- Do not require embeddings by default.

### Task 2: Optional Vector Backend Spec and Guard

**Files:**
- Modify: `docs/configuration.md`
- Test: `tests/test_document_index.py`

Required behavior:

- Add `INSIGHT_GRAPH_DOCUMENT_RETRIEVAL=deterministic|vector`.
- `vector` mode must fail safely with a sanitized error if optional dependencies/database are unavailable.
- Tests must not require PostgreSQL.

---

## Phase 14: PostgreSQL Checkpoint Resume

This phase must start with a separate design spec before code. It is not a Phase 11 blocker.

Required tasks:

1. Define resume semantics: queued job retry, interrupted node resume, final report idempotency, and stale lease behavior.
2. Create migration path for existing JSON/SQLite job metadata.
3. Add PostgreSQL test container or fake repository tests that do not require a local server by default.
4. Wire LangGraph checkpoint state to job IDs without exposing provider errors.
5. Add docs for backup, cleanup, and operational failure modes.

---

## Phase 15: pgvector Long-Term Memory

This phase must start after Phase 14 or with explicit approval to decouple memory from checkpoint storage.

Required tasks:

1. Define memory payload: task summary, entities, sections, evidence IDs, source URLs, and retention metadata.
2. Add opt-in embeddings provider with cost controls and no default network calls.
3. Add delete/export controls for privacy.
4. Add eval proof that retrieved memory improves grounded reports without increasing unsupported claims.
5. Add docs for disabling memory and purging stored embeddings.

---

## Phase 16: Production Observability and Tool Extensibility

Required tasks:

1. Add opt-in full LLM trace export that can store prompts/completions only when explicitly enabled.
2. Add token/cost summaries from provider usage metadata.
3. Add MCP-style external tool registry only after security boundaries are documented.
4. Add sandboxed `code_execute` only after resource limits, filesystem isolation, timeout, and dependency policy are specified.

---

## Verification Rules

Every implementation branch must run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Do not claim success without fresh output from these commands.

---

## Self-Review

- Spec coverage: covers the reference README gaps: multi-round collection, convergence, budgets, compression, long-document retrieval, checkpoint resume, memory, observability, MCP/code execution.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation placeholders remain.
- Scope check: Phase 11 is immediately implementable without new service dependencies. Phases 14-16 are intentionally split because they add independent infrastructure/security concerns.
- Offline safety: default behavior remains deterministic/offline; live depth is opt-in through `live-research`.
