# Multi-Provider LLM Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local-first multi-provider config presets for OpenAI-compatible LLM runtimes without enabling live LLM calls by default.

**Architecture:** Replace Qwen-only constants with a provider preset table in `src/insight_graph/llm/config.py`. `resolve_llm_config()` resolves explicit args, `INSIGHT_GRAPH_LLM_*` env vars, provider defaults, and legacy OpenAI-compatible fallbacks in one place.

**Tech Stack:** Python 3.13, Pydantic, pytest, ruff.

---

## Task 1: Provider Preset Registry

**Files:**
- Modify: `tests/test_llm_config.py`
- Modify: `src/insight_graph/llm/config.py`

- [ ] Add RED tests for `ollama`, `lmstudio`, `vllm`, and `localai` provider defaults.
- [ ] Add RED tests proving named providers ignore stale `OPENAI_BASE_URL` when `INSIGHT_GRAPH_LLM_BASE_URL` is unset.
- [ ] Refactor `config.py` to use a provider preset table with `base_url`, `model`, `api_key`, and optional provider API-key env.
- [ ] Keep existing Qwen tests passing while treating Qwen as one preset.
- [ ] Run `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_config.py -q`.
- [ ] Run `git diff --check`.
- [ ] Commit as `feat(llm): add local llm provider presets`.

## Task 2: Documentation And Roadmap

**Files:**
- Modify: `docs/configuration.md`
- Modify: `docs/reference-parity-roadmap.md`
- Modify: `CHANGELOG.md`

- [ ] Document `INSIGHT_GRAPH_LLM_PROVIDER` with supported values: `openai_compatible`, `ollama`, `lmstudio`, `vllm`, `localai`, `qwen`.
- [ ] State that provider selection only resolves config and does not enable live LLM calls.
- [ ] State local provider defaults and override rules.
- [ ] Update roadmap Phase 11 to “Multi-provider LLM config presets” implemented; keep Minimax as a future provider preset.
- [ ] Run `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_config.py tests/test_repository_hygiene.py -q`.
- [ ] Run `git diff --check`.
- [ ] Commit as `docs: document llm provider presets`.

## Task 3: Final Verification And Merge

- [ ] Run full pytest in the worktree.
- [ ] Run full ruff in the worktree.
- [ ] Run `git diff --check` in the worktree.
- [ ] Fast-forward merge `phase33-qwen-provider` into `master`.
- [ ] Re-run full pytest, ruff, and `git diff --check` on `master`.
- [ ] Remove `.worktrees/phase33-qwen-provider` and delete branch `phase33-qwen-provider`.

## Self-Review

- Scope now matches user feedback: no cloud requirement, Qwen is not privileged, more local/self-hosted LLMs are supported.
- No implementation step requires network or cloud credentials.
- Defaults remain offline because provider config is separate from live LLM provider activation.
