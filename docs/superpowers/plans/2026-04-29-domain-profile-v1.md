# Domain Profile v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 2 of `docs/report-quality-roadmap.md` by adding deterministic domain profile selection to the Planner without changing collection or report generation behavior.

**Architecture:** Add a small `insight_graph.report_quality.domain_profiles` module that owns domain profile definitions and deterministic keyword-based selection. Store only the selected profile ID on `GraphState` so later phases can consume it without coupling domain rules into `planner.py`.

**Tech Stack:** Python 3.11+, dataclasses, Pydantic `GraphState`, existing Planner tests, pytest, Ruff.

---

## Phase Context

This plan implements **Phase 2: Domain Profile v1** from `docs/report-quality-roadmap.md`.

This phase may add a focused `report_quality` package because profile definitions must be reused by Phase 4 section planning and Phase 5 collection budgets. It must not change Planner subtask order, Collector behavior, Analyst behavior, Critic behavior, Reporter output, API behavior, or live provider defaults.

## Files

- Create: `src/insight_graph/report_quality/__init__.py`
- Create: `src/insight_graph/report_quality/domain_profiles.py`
- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/agents/planner.py`
- Create: `tests/test_domain_profiles.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_graph.py`
- Modify: `docs/report-quality-roadmap.md`
- Modify: `CHANGELOG.md`

## Domain Contract

Supported profile IDs:

```python
competitive_intel
technology_trends
market_research
company_profile
```

Each profile exposes:

```python
id: str
display_name: str
report_sections: tuple[str, ...]
required_questions: tuple[str, ...]
priority_source_types: tuple[str, ...]
min_evidence_per_section: int
expected_tables: tuple[str, ...]
```

Detection precedence is deterministic: competitive intelligence, technology trends, market research, company profile, generic fallback.

## Task 1: Add Domain Profile Tests

**Files:**

- Create: `tests/test_domain_profiles.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_domain_profiles.py`:

```python
import pytest

from insight_graph.report_quality.domain_profiles import (
    DOMAIN_PROFILES,
    detect_domain_profile,
    get_domain_profile,
)


def test_domain_profiles_define_required_phase2_domains() -> None:
    assert set(DOMAIN_PROFILES) == {
        "competitive_intel",
        "technology_trends",
        "market_research",
        "company_profile",
        "generic",
    }

    for profile in DOMAIN_PROFILES.values():
        assert profile.report_sections
        assert profile.required_questions
        assert profile.priority_source_types
        assert profile.min_evidence_per_section >= 1


@pytest.mark.parametrize(
    ("query", "profile_id"),
    [
        ("Compare Cursor, OpenCode, and GitHub Copilot pricing", "competitive_intel"),
        ("Analyze AI agent architecture and technology trends", "technology_trends"),
        ("Map the AI coding tools market opportunity", "market_research"),
        ("Build a company profile for Anthropic funding and products", "company_profile"),
        ("Summarize this research topic", "generic"),
    ],
)
def test_detect_domain_profile_is_deterministic(query: str, profile_id: str) -> None:
    assert detect_domain_profile(query).id == profile_id


def test_get_domain_profile_returns_generic_for_unknown_id() -> None:
    assert get_domain_profile("missing").id == "generic"
```

- [ ] **Step 2: Verify RED**

Run: `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_domain_profiles.py -v`

Expected: FAIL because `insight_graph.report_quality` does not exist.

## Task 2: Implement Domain Profile Module

**Files:**

- Create: `src/insight_graph/report_quality/__init__.py`
- Create: `src/insight_graph/report_quality/domain_profiles.py`

- [ ] **Step 1: Add package marker**

Create `src/insight_graph/report_quality/__init__.py`:

```python
"""Report-quality support modules."""
```

- [ ] **Step 2: Add domain profile definitions and detector**

Create `src/insight_graph/report_quality/domain_profiles.py` with a frozen `DomainProfile` dataclass, five profile definitions, `DOMAIN_PROFILES`, `get_domain_profile()`, and `detect_domain_profile()`. Keyword groups must be lowercase tuples and detection must use the precedence in the Domain Contract.

- [ ] **Step 3: Verify GREEN**

Run: `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_domain_profiles.py -v`

Expected: PASS.

## Task 3: Attach Selected Profile to Planner State

**Files:**

- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/agents/planner.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Write failing Planner tests**

Add tests asserting `plan_research()` sets `state.domain_profile` to `competitive_intel`, `technology_trends`, and `generic` while preserving the existing four subtasks and tool selection behavior.

- [ ] **Step 2: Verify RED**

Run: `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py::test_planner_sets_competitive_domain_profile tests/test_agents.py::test_planner_sets_technology_domain_profile tests/test_agents.py::test_planner_uses_generic_domain_profile_as_fallback -v`

Expected: FAIL because `GraphState` has no `domain_profile` value set.

- [ ] **Step 3: Implement state and Planner integration**

Add `domain_profile: str | None = None` to `GraphState`. In `plan_research()`, call `detect_domain_profile(state.user_request)` and assign `state.domain_profile = profile.id` before building subtasks.

- [ ] **Step 4: Add graph integration assertion**

Update `test_run_research_executes_full_graph` to assert `result.domain_profile == "competitive_intel"`.

- [ ] **Step 5: Verify GREEN**

Run: `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py tests/test_graph.py -v`

Expected: PASS.

## Task 4: Update Roadmap and Changelog

**Files:**

- Modify: `docs/report-quality-roadmap.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Document Phase 2 implementation entry points**

Under Phase 2, add that initial implementation lives in `src/insight_graph/report_quality/domain_profiles.py`, stores the selected profile ID on `GraphState.domain_profile`, and leaves workflow behavior unchanged.

- [ ] **Step 2: Add changelog entry**

Under `## Unreleased`, add `- Added deterministic domain profile selection for Planner state.`

- [ ] **Step 3: Run diff check**

Run: `git diff --check`

Expected: no whitespace errors. CRLF warnings are acceptable.

## Task 5: Verification and Commit

**Files:**

- No additional files.

- [ ] **Step 1: Run targeted tests**

Run: `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_domain_profiles.py tests/test_agents.py tests/test_graph.py -v`

Expected: PASS.

- [ ] **Step 2: Run full tests**

Run: `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`

Expected: PASS.

- [ ] **Step 3: Run full Ruff**

Run: `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`

Expected: `All checks passed!`

- [ ] **Step 4: Run diff check**

Run: `git diff --check`

Expected: no whitespace errors. CRLF warnings are acceptable.

- [ ] **Step 5: Commit**

Commit message: `feat(planner): add domain profiles`

## Self-Review Notes

- Spec coverage: Covers Phase 2 required domains, profile fields, deterministic Planner selection, and tests for competitive intelligence, technology trends, and generic fallback.
- Scope: Does not change collection, analysis, reporting, API, dashboard, deployment, storage, live providers, or Eval scoring.
- Extra project quality addition: The new module is justified because Phase 4 and Phase 5 will reuse these profile definitions; keeping them outside `planner.py` prevents route logic from being tangled with subtask construction.
