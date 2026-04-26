# FastAPI Research API MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal synchronous FastAPI API for running the existing InsightGraph research workflow and returning the same safe JSON shape as CLI `--output-json`.

**Architecture:** Keep HTTP concerns in a new `src/insight_graph/api.py` module. Reuse the existing CLI preset helper and JSON payload builder so API and CLI response shapes stay aligned, while tests monkeypatch `api.run_research` to remain offline and deterministic.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, pytest, FastAPI TestClient, existing Typer CLI and GraphState models.

---

## File Structure

- Create `src/insight_graph/api.py`: FastAPI app, request model, health endpoint, research endpoint, safe workflow error handling.
- Create `tests/test_api.py`: offline API tests with `TestClient` and monkeypatched workflow.
- Modify `pyproject.toml`: add `fastapi>=0.115.0` runtime dependency.
- Modify `README.md`: document API MVP usage and explicit limits.

---

### Task 1: Add FastAPI Dependency And API Endpoints

**Files:**
- Create: `src/insight_graph/api.py`
- Create: `tests/test_api.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add failing API tests**

Create `tests/test_api.py` with:

```python
import os

from fastapi.testclient import TestClient

import insight_graph.api as api_module
from insight_graph.cli import LIVE_LLM_PRESET_DEFAULTS
from insight_graph.state import (
    CompetitiveMatrixRow,
    Critique,
    Finding,
    GraphState,
    LLMCallRecord,
    ToolCallRecord,
)


def clear_live_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_PROVIDER",
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_LLM_BASE_URL",
        "INSIGHT_GRAPH_LLM_MODEL",
        "INSIGHT_GRAPH_USE_WEB_SEARCH",
        "INSIGHT_GRAPH_SEARCH_PROVIDER",
        "INSIGHT_GRAPH_RELEVANCE_FILTER",
        "INSIGHT_GRAPH_RELEVANCE_JUDGE",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.delenv(name, raising=False)


def make_api_state(query: str) -> GraphState:
    return GraphState(
        user_request=query,
        report_markdown="# InsightGraph Research Report\n",
        findings=[
            Finding(
                title="Packaging differs",
                summary="Cursor and Copilot use different packaging signals.",
                evidence_ids=["cursor-pricing"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Cursor",
                positioning="Official product positioning signal",
                strengths=["Official/documented source coverage"],
                evidence_ids=["cursor-pricing"],
            )
        ],
        critique=Critique(passed=True, reason="Findings cite verified evidence."),
        tool_call_log=[
            ToolCallRecord(
                subtask_id="collect",
                tool_name="mock_search",
                query=query,
                evidence_count=1,
            )
        ],
        llm_call_log=[
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay-model",
                success=True,
                duration_ms=12,
            )
        ],
        iterations=1,
    )


def test_health_returns_ok() -> None:
    client = TestClient(api_module.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_research_returns_cli_aligned_json(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "  Compare AI coding agents  "})

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_request"] == "Compare AI coding agents"
    assert payload["report_markdown"] == "# InsightGraph Research Report\n"
    assert payload["findings"] == [
        {
            "title": "Packaging differs",
            "summary": "Cursor and Copilot use different packaging signals.",
            "evidence_ids": ["cursor-pricing"],
        }
    ]
    assert payload["competitive_matrix"] == [
        {
            "product": "Cursor",
            "positioning": "Official product positioning signal",
            "strengths": ["Official/documented source coverage"],
            "evidence_ids": ["cursor-pricing"],
        }
    ]
    assert payload["critique"] == {
        "passed": True,
        "reason": "Findings cite verified evidence.",
        "missing_topics": [],
    }
    assert payload["tool_call_log"][0]["tool_name"] == "mock_search"
    assert payload["llm_call_log"][0]["model"] == "relay-model"
    assert payload["iterations"] == 1


def test_research_passes_query_to_workflow(monkeypatch) -> None:
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "Compare Cursor"})

    assert response.status_code == 200
    assert observed_queries == ["Compare Cursor"]
```

- [ ] **Step 2: Run API tests and verify RED**

Run:

```powershell
python -m pytest tests/test_api.py::test_health_returns_ok tests/test_api.py::test_research_returns_cli_aligned_json tests/test_api.py::test_research_passes_query_to_workflow -q
```

Expected: FAIL because `insight_graph.api` does not exist.

- [ ] **Step 3: Add FastAPI dependency**

In `pyproject.toml`, add `fastapi>=0.115.0` to `[project].dependencies`:

```toml
dependencies = [
  "beautifulsoup4>=4.12.0",
  "ddgs>=9.0.0",
  "fastapi>=0.115.0",
  "langgraph>=0.2.0",
  "langchain-core>=0.3.0",
  "openai>=1.0.0",
  "pydantic>=2.7.0",
  "typer>=0.12.0",
  "rich>=13.7.0",
]
```

- [ ] **Step 4: Implement API module**

Create `src/insight_graph/api.py`:

```python
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

from insight_graph.cli import (
    ResearchPreset,
    _apply_research_preset,
    _build_research_json_payload,
)
from insight_graph.graph import run_research

app = FastAPI(title="InsightGraph API")


class ResearchRequest(BaseModel):
    query: str
    preset: ResearchPreset = ResearchPreset.offline

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be blank")
        return stripped


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/research")
def research(request: ResearchRequest) -> dict[str, Any]:
    _apply_research_preset(request.preset)
    try:
        state = run_research(request.query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Research workflow failed.") from exc
    return _build_research_json_payload(state)
```

- [ ] **Step 5: Run API tests and lint**

Run:

```powershell
python -m pytest tests/test_api.py::test_health_returns_ok tests/test_api.py::test_research_returns_cli_aligned_json tests/test_api.py::test_research_passes_query_to_workflow -q
python -m ruff check src/insight_graph/api.py tests/test_api.py pyproject.toml
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add pyproject.toml src/insight_graph/api.py tests/test_api.py
git commit -m "feat: add research api endpoint"
```

---

### Task 2: Add API Preset And Error Behavior Tests

**Files:**
- Modify: `tests/test_api.py`
- Modify: `src/insight_graph/api.py` only if tests reveal a behavior gap

- [ ] **Step 1: Add failing behavior tests**

Append to `tests/test_api.py`:

```python
def test_research_live_llm_preset_applies_defaults(monkeypatch) -> None:
    clear_live_env(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in LIVE_LLM_PRESET_DEFAULTS}
        )
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        json={"query": "Compare AI coding agents", "preset": "live-llm"},
    )

    assert response.status_code == 200
    assert observed_env == LIVE_LLM_PRESET_DEFAULTS


def test_research_live_llm_preset_preserves_explicit_env(monkeypatch) -> None:
    clear_live_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "deterministic")
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in LIVE_LLM_PRESET_DEFAULTS}
        )
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        json={"query": "Compare AI coding agents", "preset": "live-llm"},
    )

    assert response.status_code == 200
    assert observed_env["INSIGHT_GRAPH_SEARCH_PROVIDER"] == "mock"
    assert observed_env["INSIGHT_GRAPH_REPORTER_PROVIDER"] == "deterministic"
    assert observed_env["INSIGHT_GRAPH_USE_WEB_SEARCH"] == "1"
    assert observed_env["INSIGHT_GRAPH_ANALYST_PROVIDER"] == "llm"


def test_research_offline_preset_does_not_apply_live_defaults(monkeypatch) -> None:
    clear_live_env(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in LIVE_LLM_PRESET_DEFAULTS}
        )
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        json={"query": "Compare AI coding agents", "preset": "offline"},
    )

    assert response.status_code == 200
    assert observed_env == {name: None for name in LIVE_LLM_PRESET_DEFAULTS}


def test_research_rejects_blank_query() -> None:
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "   "})

    assert response.status_code == 422


def test_research_rejects_unknown_preset() -> None:
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        json={"query": "Compare AI coding agents", "preset": "bad"},
    )

    assert response.status_code == 422


def test_research_returns_safe_500_for_workflow_exception(monkeypatch) -> None:
    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider payload and local path")

    monkeypatch.setattr(api_module, "run_research", fail_run_research)
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "Compare AI coding agents"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Research workflow failed."}
    assert "secret provider payload" not in response.text
    assert "local path" not in response.text
```

- [ ] **Step 2: Run behavior tests**

Run:

```powershell
python -m pytest tests/test_api.py -q
```

Expected: PASS if Task 1 implementation already covers the behavior. If a test fails, update `src/insight_graph/api.py` minimally to satisfy the stated behavior.

- [ ] **Step 3: Run lint**

Run:

```powershell
python -m ruff check src/insight_graph/api.py tests/test_api.py
```

Expected: `All checks passed!`.

- [ ] **Step 4: Commit Task 2**

Run:

```powershell
git add src/insight_graph/api.py tests/test_api.py
git commit -m "test: cover research api behavior"
```

---

### Task 3: Document API MVP

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README current MVP sections**

In `README.md`, update the current output section to include API MVP details. Replace the existing API/frontend bullet:

```markdown
- **API / 前端**：尚未实现，属于后续路线图
```

with:

```markdown
- **API**：当前 MVP 提供同步 `GET /health` 和 `POST /research`，响应结构与 CLI `--output-json` 对齐，包含 `competitive_matrix`
- **前端 / WebSocket**：尚未实现，属于后续路线图
```

Add a short API usage subsection after `### 当前输出`:

```markdown
### API MVP

当前 API 是单进程同步 MVP，不包含 WebSocket、auth、持久化、后台任务或并发请求之间的环境变量隔离。

```bash
python -m pip install "uvicorn[standard]"
uvicorn insight_graph.api:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor, OpenCode, and GitHub Copilot"}'
```

`uvicorn` 是运行示例依赖，不是当前 package runtime dependency。
```

Keep the existing note that broader FastAPI/WebSocket shape remains later roadmap where it describes the target architecture.

- [ ] **Step 2: Run docs-related verification**

Run:

```powershell
python -m pytest tests/test_api.py tests/test_cli.py -q
python -m ruff check .
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 3: Commit Task 3**

Run:

```powershell
git add README.md
git commit -m "docs: document research api mvp"
```

---

### Task 4: Final Verification And API Smoke

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_api.py tests/test_cli.py tests/test_graph.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full tests and lint**

Run:

```powershell
python -m pytest -q
python -m ruff check .
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 3: Reinstall editable checkout**

Run:

```powershell
python -m pip install -e .
```

Expected: command succeeds and installs the current checkout.

- [ ] **Step 4: Run API import smoke**

Run:

```powershell
python -c "from insight_graph.api import app; print(app.title)"
```

Expected output:

```text
InsightGraph API
```

- [ ] **Step 5: Run TestClient API smoke**

Run:

```powershell
python -c "from fastapi.testclient import TestClient; from insight_graph.api import app; client=TestClient(app); print(client.get('/health').json()['status'])"
```

Expected output:

```text
ok
```

- [ ] **Step 6: Inspect git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree on the implementation branch.
