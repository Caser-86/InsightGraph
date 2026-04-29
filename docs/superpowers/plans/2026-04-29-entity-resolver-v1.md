# Entity Resolver v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 3 of `docs/report-quality-roadmap.md` by adding deterministic entity resolution for product/company names without changing collection behavior yet.

**Architecture:** Add `insight_graph.report_quality.entity_resolver` with small dataclasses and deterministic alias matching. Store resolved entities on `GraphState.resolved_entities` as serializable dicts so later phases can build targeted section queries without coupling resolver internals to Planner.

**Tech Stack:** Python 3.11+, dataclasses, Pydantic `GraphState`, pytest, Ruff.

---

## Phase Context

This plan implements **Phase 3: Entity Resolver v1**. It may add a focused resolver module because later section planning and collection need canonical names, aliases, entity type, and optional official domain hints.

## Files

- Create: `src/insight_graph/report_quality/entity_resolver.py`
- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/agents/planner.py`
- Create: `tests/test_entity_resolver.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_graph.py`
- Modify: `docs/report-quality-roadmap.md`
- Modify: `CHANGELOG.md`

## Contract

Resolver returns deterministic entities with:

```python
id: str
name: str
entity_type: str
aliases: tuple[str, ...]
official_domains: tuple[str, ...]
query_terms: tuple[str, ...]
```

Initial known entities: Cursor, OpenCode, Claude Code, GitHub Copilot, Codeium, Windsurf, Anthropic, OpenAI, GitHub.

Unknown capitalized product/company-like names may be returned as `unknown` entities with normalized IDs and no official domains. Generic words must not become entities.

## Task 1: Add Entity Resolver Tests

- [ ] Create `tests/test_entity_resolver.py` with tests for known entity resolution, alias matching, dedupe, generic fallback, and unknown capitalized entity extraction.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_entity_resolver.py -v` and verify RED because module is missing.

## Task 2: Implement Entity Resolver Module

- [ ] Create `src/insight_graph/report_quality/entity_resolver.py` with `ResolvedEntity`, `KNOWN_ENTITIES`, `resolve_entities()`, and helpers.
- [ ] Keep matching deterministic and offline. Known entity matching should be alias-based and case-insensitive.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_entity_resolver.py -v` and verify GREEN.

## Task 3: Attach Resolved Entities to Planner State

- [ ] Add failing Planner tests asserting `plan_research()` populates `state.resolved_entities` for Cursor/GitHub Copilot and leaves it empty for generic requests.
- [ ] Add `resolved_entities: list[dict[str, object]] = Field(default_factory=list)` to `GraphState`.
- [ ] In `plan_research()`, call `resolve_entities(state.user_request)` and store `[entity.to_payload() ...]`.
- [ ] Update graph test to assert a known competitive query resolves entities.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py tests/test_graph.py -v` and verify GREEN.

## Task 4: Docs

- [ ] Update Phase 3 in `docs/report-quality-roadmap.md` to mention `entity_resolver.py` and `GraphState.resolved_entities`.
- [ ] Add changelog entry: `- Added deterministic entity resolution for Planner state.`
- [ ] Run `git diff --check`.

## Task 5: Verification and Commit

- [ ] Run targeted tests: `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_entity_resolver.py tests/test_agents.py tests/test_graph.py -v`
- [ ] Run full tests: `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`
- [ ] Run full Ruff: `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`
- [ ] Run `git diff --check`.
- [ ] Commit: `feat(planner): resolve research entities`

## Self-Review Notes

- Scope stays inside Phase 3. No collection, reporting, API, dashboard, storage, or provider behavior changes.
- Extra module is justified because Phase 4 and Phase 5 need entity data independently from Planner subtask construction.
