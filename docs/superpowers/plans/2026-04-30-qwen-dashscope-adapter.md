# Qwen/DashScope Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `INSIGHT_GRAPH_LLM_PROVIDER=qwen` config sugar for DashScope's OpenAI-compatible API without changing offline defaults.

**Architecture:** Extend `LLMConfig` and `resolve_llm_config()` with a validated provider field and provider-specific defaults. Keep `OpenAICompatibleChatClient` unchanged except for carrying the provider metadata through config.

**Tech Stack:** Python 3.13, Pydantic models, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/llm/config.py`: add provider constants, provider validation, and Qwen/DashScope default resolution.
- Modify `tests/test_llm_config.py`: add config-only tests for Qwen defaults, override precedence, DashScope API key fallback, and unknown provider rejection.
- Modify `docs/configuration.md`: document Qwen provider env vars and override behavior.
- Modify `docs/reference-parity-roadmap.md`: mark Phase 11 implemented and move Next Phase to Minimax adapter.
- Modify `CHANGELOG.md`: add an Unreleased note for the named Qwen/DashScope provider.

### Task 1: Add Qwen Provider Config Resolution

**Files:**
- Modify: `tests/test_llm_config.py`
- Modify: `src/insight_graph/llm/config.py`

- [ ] **Step 1: Write failing provider tests**

Add these tests to `tests/test_llm_config.py` after the existing fallback tests:

```python
def test_resolve_llm_config_defaults_to_openai_compatible_provider(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_PROVIDER", raising=False)

    config = resolve_llm_config()

    assert config.provider == "openai_compatible"


def test_resolve_llm_config_qwen_provider_sets_dashscope_defaults(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_PROVIDER", "qwen")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    config = resolve_llm_config()

    assert config.provider == "qwen"
    assert config.api_key == "dashscope-key"
    assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config.model == "qwen-plus"


def test_resolve_llm_config_qwen_provider_allows_explicit_overrides(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_PROVIDER", "qwen")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "custom-qwen")

    config = resolve_llm_config(
        api_key="explicit-key",
        base_url="https://explicit.example/v1",
        model="explicit-model",
    )

    assert config.provider == "qwen"
    assert config.api_key == "explicit-key"
    assert config.base_url == "https://explicit.example/v1"
    assert config.model == "explicit-model"


def test_resolve_llm_config_qwen_provider_env_overrides_defaults(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_PROVIDER", "qwen")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "insight-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "qwen-max")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    config = resolve_llm_config()

    assert config.provider == "qwen"
    assert config.api_key == "insight-key"
    assert config.base_url == "https://relay.example/v1"
    assert config.model == "qwen-max"


def test_resolve_llm_config_rejects_unknown_provider(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_PROVIDER", "not-real")

    with pytest.raises(ValueError, match="provider"):
        resolve_llm_config()
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_config.py -q
```

Expected: fail because `LLMConfig` has no `provider` field and `resolve_llm_config()` does not know Qwen defaults.

- [ ] **Step 3: Implement provider config**

Update `src/insight_graph/llm/config.py` to include these constants and helpers near existing wire API constants:

```python
DEFAULT_LLM_PROVIDER = "openai_compatible"
QWEN_LLM_PROVIDER = "qwen"
SUPPORTED_LLM_PROVIDERS = frozenset({DEFAULT_LLM_PROVIDER, QWEN_LLM_PROVIDER})
QWEN_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_DEFAULT_MODEL = "qwen-plus"
```

Add `provider: str = DEFAULT_LLM_PROVIDER` to `LLMConfig`, and add a validator:

```python
    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        if value not in SUPPORTED_LLM_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_LLM_PROVIDERS))
            raise ValueError(
                f"Unsupported provider: {value}. Supported values: {supported}"
            )
        return value
```

Change `resolve_llm_config()` signature to include `provider: str | None = None`. Resolve provider before constructing `LLMConfig`:

```python
    resolved_provider = provider or os.getenv("INSIGHT_GRAPH_LLM_PROVIDER") or DEFAULT_LLM_PROVIDER
    qwen_selected = resolved_provider == QWEN_LLM_PROVIDER
```

Pass `provider=resolved_provider` into `LLMConfig`. Resolve fields with this precedence:

```python
api_key=(
    api_key
    if api_key is not None
    else os.getenv("INSIGHT_GRAPH_LLM_API_KEY")
    or (os.getenv("DASHSCOPE_API_KEY") if qwen_selected else None)
    or os.getenv("OPENAI_API_KEY")
),
base_url=(
    base_url
    if base_url is not None
    else os.getenv("INSIGHT_GRAPH_LLM_BASE_URL")
    or os.getenv("OPENAI_BASE_URL")
    or (QWEN_DASHSCOPE_BASE_URL if qwen_selected else None)
),
model=(
    model
    if model is not None
    else os.getenv("INSIGHT_GRAPH_LLM_MODEL")
    or (QWEN_DEFAULT_MODEL if qwen_selected else "gpt-4o-mini")
),
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_config.py -q
```

Expected: all `test_llm_config.py` tests pass.

- [ ] **Step 5: Commit provider config**

Run:

```powershell
git add src/insight_graph/llm/config.py tests/test_llm_config.py
git commit -m "feat(llm): add qwen provider config"
```

### Task 2: Document Qwen Provider And Roadmap

**Files:**
- Modify: `docs/configuration.md`
- Modify: `docs/reference-parity-roadmap.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update docs**

Add a short Qwen subsection in `docs/configuration.md` near existing LLM Analyst configuration:

```markdown
### Qwen/DashScope Provider

Set `INSIGHT_GRAPH_LLM_PROVIDER=qwen` to use DashScope's OpenAI-compatible endpoint. The provider supplies `https://dashscope.aliyuncs.com/compatible-mode/v1` and `qwen-plus` when `INSIGHT_GRAPH_LLM_BASE_URL` and `INSIGHT_GRAPH_LLM_MODEL` are unset. API key resolution is `INSIGHT_GRAPH_LLM_API_KEY`, then `DASHSCOPE_API_KEY`, then `OPENAI_API_KEY`.

Explicit `resolve_llm_config(...)` arguments and `INSIGHT_GRAPH_LLM_*` environment variables override provider defaults. This does not change offline defaults; live LLM use still requires explicit provider/preset configuration.
```

In `docs/reference-parity-roadmap.md`, mark Phase 11 implemented and move Next Phase to Phase 12 Minimax adapter.

In `CHANGELOG.md`, add:

```markdown
- Added `INSIGHT_GRAPH_LLM_PROVIDER=qwen` config sugar for DashScope's OpenAI-compatible endpoint.
```

- [ ] **Step 2: Run focused docs-adjacent tests**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_config.py tests/test_repository_hygiene.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit docs**

Run:

```powershell
git add docs/configuration.md docs/reference-parity-roadmap.md CHANGELOG.md
git commit -m "docs: document qwen provider config"
```

### Task 3: Final Verification And Merge

**Files:**
- Verify all changed files from Tasks 1-2.

- [ ] **Step 1: Run full tests**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
```

Expected: full suite passes with only the existing intentional skip.

- [ ] **Step 2: Run ruff**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 3: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no output except acceptable Windows CRLF warnings before files are committed.

- [ ] **Step 4: Merge back to master and re-verify**

From `D:\Files\opencode.files`, run:

```powershell
git merge --ff-only phase33-qwen-provider
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: fast-forward merge; full test suite passes; ruff passes; whitespace check has no output.

- [ ] **Step 5: Cleanup worktree and branch**

Run:

```powershell
git worktree remove "D:\Files\opencode.files\.worktrees\phase33-qwen-provider"
git branch -d phase33-qwen-provider
git status --short --branch
```

Expected: worktree removed, branch deleted, master clean except expected ahead count.

## Self-Review

- Spec coverage: provider selection, DashScope defaults, override precedence, API key fallback, unknown provider rejection, docs, roadmap, and verification are covered.
- Placeholder scan: no placeholders or deferred requirements remain.
- Type consistency: plan uses `provider`, `DEFAULT_LLM_PROVIDER`, `QWEN_LLM_PROVIDER`, `QWEN_DASHSCOPE_BASE_URL`, and `QWEN_DEFAULT_MODEL` consistently.
