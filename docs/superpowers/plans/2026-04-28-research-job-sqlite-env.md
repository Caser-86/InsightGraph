# Research Job SQLite Environment Enablement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable the SQLite research job backend at runtime through explicit environment variables.

**Architecture:** Keep `research_jobs.py` as the service layer and default to the in-memory backend. Add small env parsing helpers in `research_jobs_store.py`, then configure the active backend from those helpers during module initialization and in tests.

**Tech Stack:** Python 3.11+, stdlib `os`/`pathlib`, pytest monkeypatch, existing research job backends.

---

## File Structure

- Modify: `src/insight_graph/research_jobs_store.py`
  - Own env variable names and parsing for backend selection and SQLite path.
- Modify: `src/insight_graph/research_jobs.py`
  - Configure the default backend from env.
  - Keep test helper configuration functions.
- Modify: `tests/test_research_jobs.py`
  - Cover default memory env, SQLite env selection, missing path failure, unknown backend failure, and JSON import with SQLite.
- Modify: `docs/research-jobs-api.md`
  - Document runtime env variables.
- Modify: `docs/research-job-repository-contract.md`
  - Document explicit env selection.

## Task 1: Add Env Parsing Helpers

**Files:**
- Modify: `src/insight_graph/research_jobs_store.py`
- Modify: `tests/test_research_jobs_store.py`

- [ ] **Step 1: Write failing env helper tests**

Add to `tests/test_research_jobs_store.py`:

```python
def test_research_jobs_backend_from_env_defaults_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", raising=False)

    assert research_jobs_backend_from_env() == "memory"


def test_research_jobs_backend_from_env_accepts_sqlite(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", "sqlite")

    assert research_jobs_backend_from_env() == "sqlite"


def test_research_jobs_backend_from_env_rejects_unknown_backend(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", "postgres")

    with pytest.raises(ResearchJobsStoreError, match="Unknown research jobs backend"):
        research_jobs_backend_from_env()


def test_research_jobs_sqlite_path_from_env_requires_value(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", raising=False)

    with pytest.raises(ResearchJobsStoreError, match="SQLite research jobs path is required"):
        research_jobs_sqlite_path_from_env()


def test_research_jobs_sqlite_path_from_env_returns_path(monkeypatch, tmp_path) -> None:
    path = tmp_path / "jobs.sqlite3"
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", str(path))

    assert research_jobs_sqlite_path_from_env() == path
```

Add imports:

```python
from insight_graph.research_jobs_store import (
    research_jobs_backend_from_env,
    research_jobs_sqlite_path_from_env,
)
```

- [ ] **Step 2: Run env helper tests to verify RED**

Run: `python -m pytest tests/test_research_jobs_store.py::test_research_jobs_backend_from_env_defaults_to_memory tests/test_research_jobs_store.py::test_research_jobs_sqlite_path_from_env_requires_value -v`

Expected: FAIL with import error for missing helper functions.

- [ ] **Step 3: Implement env helpers**

Add to `src/insight_graph/research_jobs_store.py`:

```python
RESEARCH_JOBS_BACKEND_ENV = "INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND"
RESEARCH_JOBS_SQLITE_PATH_ENV = "INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH"


def research_jobs_backend_from_env() -> str:
    value = os.environ.get(RESEARCH_JOBS_BACKEND_ENV, "memory").strip().lower()
    if value in {"", "memory"}:
        return "memory"
    if value == "sqlite":
        return "sqlite"
    raise ResearchJobsStoreError(f"Unknown research jobs backend: {value}")


def research_jobs_sqlite_path_from_env() -> Path:
    value = os.environ.get(RESEARCH_JOBS_SQLITE_PATH_ENV)
    if value is None or not value.strip():
        raise ResearchJobsStoreError("SQLite research jobs path is required.")
    return Path(value)
```

- [ ] **Step 4: Run env helper tests to verify GREEN**

Run: `python -m pytest tests/test_research_jobs_store.py -v`

Expected: PASS.

## Task 2: Configure Service Backend From Env

**Files:**
- Modify: `src/insight_graph/research_jobs.py`
- Modify: `tests/test_research_jobs.py`

- [ ] **Step 1: Write failing backend selection tests**

Add to `tests/test_research_jobs.py`:

```python
def test_configure_research_jobs_backend_from_env_defaults_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", raising=False)

    jobs_module.configure_research_jobs_backend_from_env()

    try:
        assert jobs_module._RESEARCH_JOBS_BACKEND.__class__.__name__ == "InMemoryResearchJobsBackend"
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()


def test_configure_research_jobs_backend_from_env_selects_sqlite(monkeypatch, tmp_path) -> None:
    sqlite_path = tmp_path / "jobs.sqlite3"
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", "sqlite")
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", str(sqlite_path))

    jobs_module.configure_research_jobs_backend_from_env()
    try:
        created = jobs_module.create_research_job(
            query="Env SQLite",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )
        detail = jobs_module.get_research_job(created["job_id"])
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()

    assert sqlite_path.exists()
    assert detail["status"] == "queued"


def test_configure_research_jobs_backend_from_env_fails_without_sqlite_path(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", "sqlite")
    monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", raising=False)

    with pytest.raises(ResearchJobsStoreError, match="SQLite research jobs path is required"):
        jobs_module.configure_research_jobs_backend_from_env()
```

- [ ] **Step 2: Run backend selection tests to verify RED**

Run: `python -m pytest tests/test_research_jobs.py::test_configure_research_jobs_backend_from_env_selects_sqlite -v`

Expected: FAIL with missing `configure_research_jobs_backend_from_env`.

- [ ] **Step 3: Implement service env configuration**

Update imports in `src/insight_graph/research_jobs.py`:

```python
from insight_graph.research_jobs_store import (
    ResearchJobsStoreError,
    load_research_jobs,
    research_jobs_backend_from_env,
    research_jobs_path_from_env,
    research_jobs_sqlite_path_from_env,
    save_research_jobs,
)
```

Add helper:

```python
def _make_research_jobs_backend_from_env() -> Any:
    backend = research_jobs_backend_from_env()
    if backend == "sqlite":
        from insight_graph.research_jobs_sqlite_backend import SQLiteResearchJobsBackend

        sqlite_backend = SQLiteResearchJobsBackend(research_jobs_sqlite_path_from_env())
        sqlite_backend.initialize()
        return sqlite_backend
    return InMemoryResearchJobsBackend(
        store_path=_RESEARCH_JOBS_PATH,
        jobs=_JOBS,
        lock=_JOBS_LOCK,
    )
```

Add public configuration helper:

```python
def configure_research_jobs_backend_from_env() -> None:
    global _NEXT_JOB_SEQUENCE, _RESEARCH_JOBS_BACKEND

    _RESEARCH_JOBS_BACKEND = _make_research_jobs_backend_from_env()
    _NEXT_JOB_SEQUENCE = _RESEARCH_JOBS_BACKEND.next_sequence()
```

Replace initial `_RESEARCH_JOBS_BACKEND = InMemoryResearchJobsBackend(...)` with a call after the helper exists, or keep initial memory backend and call `configure_research_jobs_backend_from_env()` at module import after function definitions.

- [ ] **Step 4: Run backend selection tests to verify GREEN**

Run: `python -m pytest tests/test_research_jobs.py::test_configure_research_jobs_backend_from_env_defaults_to_memory tests/test_research_jobs.py::test_configure_research_jobs_backend_from_env_selects_sqlite tests/test_research_jobs.py::test_configure_research_jobs_backend_from_env_fails_without_sqlite_path -v`

Expected: PASS.

## Task 3: Document Runtime Env Config

**Files:**
- Modify: `docs/research-jobs-api.md`
- Modify: `docs/research-job-repository-contract.md`

- [ ] **Step 1: Update docs**

Add to `docs/research-jobs-api.md` a short configuration section:

```markdown
## Runtime Storage Configuration

- Default: in-memory research job storage.
- `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=memory`: explicit in-memory storage.
- `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite`: use SQLite storage.
- `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/path/jobs.sqlite3`: required when backend is `sqlite`.
- `INSIGHT_GRAPH_RESEARCH_JOBS_PATH=/path/jobs.json`: existing JSON metadata path. With SQLite selected, this is only used as an optional import source during startup initialization.
```

Add to `docs/research-job-repository-contract.md` under service/backend boundary:

```markdown
- Runtime backend selection is explicit via `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND`; SQLite also requires `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH`.
```

- [ ] **Step 2: Verify docs and focused tests**

Run:

```bash
git diff --check
python -m pytest tests/test_research_jobs_store.py tests/test_research_jobs.py
python -m ruff check .
```

Expected: all commands exit 0.

## Final Verification

Run:

```bash
python -m pytest
python -m ruff check .
git status --short --branch
```

Expected:

- `pytest`: all tests pass.
- `ruff`: no issues.
- `git status`: clean after commit.
