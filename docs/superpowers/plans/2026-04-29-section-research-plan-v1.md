# Section Research Plan v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 4 of `docs/report-quality-roadmap.md` by deriving deterministic section-level research plans from the selected domain profile and resolved entities.

**Architecture:** Add `insight_graph.report_quality.research_plan` with serializable section plan payloads. Planner stores `GraphState.section_research_plan` while keeping the existing four LangGraph subtasks unchanged.

**Tech Stack:** Python 3.11+, dataclasses, Pydantic `GraphState`, pytest, Ruff.

---

## Phase Context

This implements **Phase 4: Section-Based Research Plan**. It prepares structured section work for later collectors, but does not change Collector behavior yet.

## Files

- Create: `src/insight_graph/report_quality/research_plan.py`
- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/agents/planner.py`
- Create: `tests/test_research_plan.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_graph.py`
- Modify: `docs/report-quality-roadmap.md`
- Modify: `CHANGELOG.md`

## Tasks

1. Add failing tests for section plan construction from competitive and generic profiles.
2. Implement `SectionResearchPlan` and `build_section_research_plan()`.
3. Store section plan payloads on `GraphState.section_research_plan` in Planner.
4. Update docs and changelog.
5. Verify targeted tests, full pytest, ruff, diff check, then commit `feat(planner): add section research plan`.

## Self-Review Notes

- Scope is Phase 4 only. No collection, scoring, citation validation, API, dashboard, or provider behavior changes.
- Extra module is justified because Phase 5 consumes section plans independently from Planner subtask construction.
