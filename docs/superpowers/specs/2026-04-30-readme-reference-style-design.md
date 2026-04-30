# README Reference-Style Redesign

## Goal

Rewrite `README.md` in the product-oriented style of the provided `wenyi-research-agent` README while keeping InsightGraph's actual implemented capabilities accurate.

## Design

The README should lead with product positioning instead of internal phase history. It should present InsightGraph as a LangGraph-based multi-agent business intelligence research engine whose target mode is networked research with search, URL/PDF fetching, verified evidence, and report generation. Offline deterministic behavior should be described as the test/CI safety baseline and fallback mode, not as the product's default value proposition.

## Structure

Use the reference README's flow:

- product introduction
- project structure
- core features table
- architecture diagram
- end-to-end execution flow
- multi-agent workflow
- evidence/data flow
- technology stack
- built-in tools
- execution chain details
- example output shape and metrics
- highlights
- quick start
- configuration
- scripts
- license

## Accuracy Rules

- Do not claim cloud-only providers are required.
- Present networked search as the intended product direction, while being precise about which commands/env vars enable live providers today.
- Do not claim external vector RAG, MCP runtime invocation, or code execution are generally enabled.
- Keep PostgreSQL checkpoint and pgvector memory described as opt-in adapters unless the current roadmap phase changes them.
- Preserve the safety posture: tests and CI remain offline and deterministic; product docs should still explain how to enable live search explicitly today.

## Verification

Run the repository tests and lint after the README rewrite. At minimum, run repository hygiene tests, `ruff`, `pytest`, and `git diff --check` before merging.
