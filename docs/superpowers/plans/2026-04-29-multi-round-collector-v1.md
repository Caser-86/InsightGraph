# Multi-Round Collector v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 5 baseline by adding deterministic section collection status from section research plans.

**Architecture:** Keep existing tool execution unchanged for compatibility. Add per-section sufficiency metadata to `GraphState.section_collection_status` so later follow-up query loops can act on missing sections.

**Tech Stack:** Python 3.11+, Pydantic `GraphState`, pytest, Ruff.

---

## Tasks

1. Add failing executor tests for section collection status.
2. Add `section_collection_status` to `GraphState` and populate it in Executor after evidence dedupe.
3. Update roadmap and changelog.
4. Verify targeted tests, full pytest, ruff, diff check, then commit `feat(collector): track section evidence status`.

## Self-Review Notes

- This is Phase 5 baseline only. It does not add live network calls, change tool counts, or perform follow-up queries yet.
