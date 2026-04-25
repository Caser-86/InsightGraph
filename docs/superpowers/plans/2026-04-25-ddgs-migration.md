# DDGS Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `duckduckgo-search` with `ddgs` so live search stops emitting the package rename warning.

**Architecture:** Keep the public search provider name `duckduckgo` unchanged and only replace the package dependency plus `DDGS` import source. Existing fake-client tests continue to cover result mapping without network access, while one focused test proves `_create_duckduckgo_client()` uses `ddgs.DDGS`.

**Tech Stack:** Python 3.13, pyproject dependencies, pytest, ruff, ddgs.

---

## File Structure

- Modify `pyproject.toml`: replace `duckduckgo-search>=6.0.0` with `ddgs>=9.0.0`.
- Modify `src/insight_graph/tools/search_providers.py`: import `DDGS` from `ddgs` in `_create_duckduckgo_client()`.
- Modify `tests/test_search_providers.py`: add coverage that `_create_duckduckgo_client()` instantiates `ddgs.DDGS`, while existing provider/mapping tests stay unchanged.

---

### Task 1: Replace DuckDuckGo Dependency And Import

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/insight_graph/tools/search_providers.py`
- Modify: `tests/test_search_providers.py`

- [ ] **Step 1: Write failing import-source test**

In `tests/test_search_providers.py`, update the import list to include `_create_duckduckgo_client`:

```python
from insight_graph.tools.search_providers import (
    DuckDuckGoSearchProvider,
    MockSearchProvider,
    SearchResult,
    _create_duckduckgo_client,
    get_search_provider,
    parse_search_limit,
)
```

Add this test after `test_get_search_provider_reads_duckduckgo_from_env()`:

```python
def test_create_duckduckgo_client_uses_ddgs_package() -> None:
    client = _create_duckduckgo_client()

    assert type(client).__module__ == "ddgs"
```

- [ ] **Step 2: Run test to verify it fails before implementation**

Run:

```bash
python -m pytest tests/test_search_providers.py::test_create_duckduckgo_client_uses_ddgs_package -q
```

Expected: FAIL because `_create_duckduckgo_client()` currently instantiates `duckduckgo_search.duckduckgo_search.DDGS` and emits the rename warning.

- [ ] **Step 3: Replace dependency**

In `pyproject.toml`, replace:

```toml
  "duckduckgo-search>=6.0.0",
```

with:

```toml
  "ddgs>=9.0.0",
```

- [ ] **Step 4: Replace import source**

In `src/insight_graph/tools/search_providers.py`, change `_create_duckduckgo_client()` from:

```python
def _create_duckduckgo_client() -> Any:
    from duckduckgo_search import DDGS

    return DDGS()
```

to:

```python
def _create_duckduckgo_client() -> Any:
    from ddgs import DDGS

    return DDGS()
```

- [ ] **Step 5: Run focused tests and lint**

Run:

```bash
python -m pytest tests/test_search_providers.py tests/test_web_search.py -q
python -m ruff check src/insight_graph/tools/search_providers.py tests/test_search_providers.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add pyproject.toml src/insight_graph/tools/search_providers.py tests/test_search_providers.py
git commit -m "chore: migrate duckduckgo search dependency to ddgs"
```

---

### Task 2: Final Verification And Live Smoke

**Files:**
- Verify: entire repository

- [ ] **Step 1: Reinstall current checkout**

Run:

```bash
python -m pip install -e .
```

Expected: command succeeds and installs `insightgraph==0.1.0` from the current working directory with `ddgs` dependency available.

- [ ] **Step 2: Run full tests and lint**

Run:

```bash
python -m pytest -v
python -m ruff check .
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 3: Run live JSON smoke and check warning is gone**

Run:

```powershell
$names = @("INSIGHT_GRAPH_LLM_API_KEY", "INSIGHT_GRAPH_LLM_BASE_URL", "INSIGHT_GRAPH_LLM_MODEL"); foreach ($name in $names) { $value = [Environment]::GetEnvironmentVariable($name, "User"); if (-not [string]::IsNullOrWhiteSpace($value)) { [Environment]::SetEnvironmentVariable($name, $value, "Process"); Set-Item -Path "env:$name" -Value $value } }; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --output-json
```

Expected:

- No `duckduckgo_search` rename warning appears in stderr/stdout.
- Workflow completes and emits parseable JSON.
- If live search returns no evidence, `tool_call_log` still shows failed `web_search` and successful `mock_search` fallback records.
- If LLM stages run, `llm_call_log` still includes token fields when provider usage is returned.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected: clean working tree on the implementation branch.
