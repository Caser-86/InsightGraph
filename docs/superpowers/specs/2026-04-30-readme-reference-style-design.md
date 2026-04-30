# README Reference-Style Redesign

## Goal

Rewrite `README.md` in the product-oriented style of the provided `wenyi-research-agent` README while keeping InsightGraph's actual implemented capabilities accurate.

## Design

The README should lead with product positioning instead of internal phase history. It should present InsightGraph as a LangGraph-based multi-agent business intelligence research engine with offline deterministic defaults and explicit opt-ins for live search, LLMs, persistence, memory, and full traces.

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
- Do not present optional/live/network behavior as default.
- Do not claim external vector RAG, MCP runtime invocation, or code execution are generally enabled.
- Keep PostgreSQL checkpoint and pgvector memory described as opt-in adapters unless the current roadmap phase changes them.
- Preserve the safety posture: default CLI/tests are offline and deterministic.

## Verification

Run the repository tests and lint after the README rewrite. At minimum, run repository hygiene tests, `ruff`, `pytest`, and `git diff --check` before merging.
