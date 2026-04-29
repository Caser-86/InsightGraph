# Live URL Revalidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate Reporter reference URLs in live research mode while keeping normal runs offline.

**Architecture:** Add a small URL validation helper that uses the existing bounded HTTP client. Reporter opts into validation through `INSIGHT_GRAPH_REPORTER_VALIDATE_URLS`; `live-research` preset sets that environment variable. Validation metadata is stored on `GraphState` and rendered as honest Reference annotations.

**Tech Stack:** Python 3.11+, Pydantic state models, pytest, ruff.

---

### Task 1: URL Validation State And Helper

**Files:**
- Modify: `src/insight_graph/state.py`
- Create: `src/insight_graph/report_quality/url_validation.py`
- Modify: `tests/test_state.py`
- Create: `tests/test_url_validation.py`

- [ ] **Step 1: Write failing tests**

Add `assert state.url_validation == []` to `test_collection_depth_metadata_defaults_are_backward_compatible()` in `tests/test_state.py`.

Create `tests/test_url_validation.py`:

```python
import importlib

from insight_graph.report_quality.url_validation import validate_evidence_url
from insight_graph.state import Evidence
from insight_graph.tools.http_client import FetchedPage, FetchError


def test_validate_evidence_url_records_success(monkeypatch) -> None:
    validation_module = importlib.import_module("insight_graph.report_quality.url_validation")

    def fake_fetch_text(url: str, timeout: float = 10.0):
        assert url == "https://example.com/source"
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html",
            text="ok",
        )

    monkeypatch.setattr(validation_module, "fetch_text", fake_fetch_text)
    evidence = Evidence(
        id="source",
        subtask_id="collect",
        title="Source",
        source_url="https://example.com/source",
        snippet="Source snippet.",
        verified=True,
    )

    result = validate_evidence_url(evidence)

    assert result == {
        "evidence_id": "source",
        "source_url": "https://example.com/source",
        "valid": True,
        "status_code": 200,
        "error": None,
    }


def test_validate_evidence_url_records_failure(monkeypatch) -> None:
    validation_module = importlib.import_module("insight_graph.report_quality.url_validation")

    def fake_fetch_text(url: str, timeout: float = 10.0):
        raise FetchError("Network error while fetching URL: timeout")

    monkeypatch.setattr(validation_module, "fetch_text", fake_fetch_text)
    evidence = Evidence(
        id="source",
        subtask_id="collect",
        title="Source",
        source_url="https://example.com/source",
        snippet="Source snippet.",
        verified=True,
    )

    result = validate_evidence_url(evidence)

    assert result == {
        "evidence_id": "source",
        "source_url": "https://example.com/source",
        "valid": False,
        "status_code": None,
        "error": "Network error while fetching URL: timeout",
    }
```

- [ ] **Step 2: Run tests to verify RED**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_state.py::test_collection_depth_metadata_defaults_are_backward_compatible tests/test_url_validation.py -v`

Expected: import/state attribute failures.

- [ ] **Step 3: Implement minimal code**

Add to `GraphState` in `src/insight_graph/state.py`:

```python
url_validation: list[dict[str, object]] = Field(default_factory=list)
```

Create `src/insight_graph/report_quality/url_validation.py`:

```python
from insight_graph.state import Evidence
from insight_graph.tools.http_client import FetchError, fetch_text


def validate_evidence_url(evidence: Evidence) -> dict[str, object]:
    try:
        page = fetch_text(evidence.source_url)
    except FetchError as exc:
        return {
            "evidence_id": evidence.id,
            "source_url": evidence.source_url,
            "valid": False,
            "status_code": None,
            "error": str(exc),
        }
    return {
        "evidence_id": evidence.id,
        "source_url": evidence.source_url,
        "valid": True,
        "status_code": page.status_code,
        "error": None,
    }
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_state.py::test_collection_depth_metadata_defaults_are_backward_compatible tests/test_url_validation.py -q`

Expected: tests pass.

### Task 2: Reporter Integration

**Files:**
- Modify: `src/insight_graph/agents/reporter.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Write failing tests**

Add tests near existing Reporter tests in `tests/test_agents.py`:

```python
def test_reporter_does_not_validate_urls_by_default(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    reporter_module = __import__("insight_graph.agents.reporter", fromlist=["reporter"])

    def fake_validate_evidence_url(evidence):
        raise AssertionError("URL validation should be opt-in")

    monkeypatch.delenv("INSIGHT_GRAPH_REPORTER_VALIDATE_URLS", raising=False)
    monkeypatch.setattr(reporter_module, "validate_evidence_url", fake_validate_evidence_url)

    updated = write_report(make_reporter_state())

    assert updated.url_validation == []


def test_reporter_validates_urls_when_enabled(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    reporter_module = __import__("insight_graph.agents.reporter", fromlist=["reporter"])

    def fake_validate_evidence_url(evidence):
        return {
            "evidence_id": evidence.id,
            "source_url": evidence.source_url,
            "valid": evidence.id != "copilot-docs",
            "status_code": 200 if evidence.id != "copilot-docs" else None,
            "error": None if evidence.id != "copilot-docs" else "Network error",
        }

    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_VALIDATE_URLS", "1")
    monkeypatch.setattr(reporter_module, "validate_evidence_url", fake_validate_evidence_url)

    updated = write_report(make_reporter_state())

    assert [item["evidence_id"] for item in updated.url_validation] == [
        "cursor-pricing",
        "copilot-docs",
    ]
    assert "[1] Cursor Pricing. https://cursor.com/pricing (URL validated)" in updated.report_markdown
    assert "[2] GitHub Copilot Documentation. https://docs.github.com/en/copilot (URL validation failed: Network error)" in updated.report_markdown
```

- [ ] **Step 2: Run tests to verify RED**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py::test_reporter_does_not_validate_urls_by_default tests/test_agents.py::test_reporter_validates_urls_when_enabled -v`

Expected: fails because Reporter has no validation hook.

- [ ] **Step 3: Implement minimal code**

In `src/insight_graph/agents/reporter.py`, import `validate_evidence_url`, add env helper, run validation after verified evidence selection in deterministic and LLM paths, and annotate references:

```python
from insight_graph.report_quality.url_validation import validate_evidence_url

REPORTER_VALIDATE_URLS_ENV = "INSIGHT_GRAPH_REPORTER_VALIDATE_URLS"


def _url_validation_enabled() -> bool:
    return os.getenv(REPORTER_VALIDATE_URLS_ENV, "").lower() in {"1", "true", "yes"}


def _maybe_validate_reference_urls(state: GraphState, evidence: list[Evidence]) -> None:
    if not _url_validation_enabled():
        return
    state.url_validation = [validate_evidence_url(item) for item in evidence]
```

Call `_maybe_validate_reference_urls(state, verified_evidence)` before `_build_reference_numbers()` in both deterministic and LLM reporter paths.

Update `_build_references_section()` to call `_reference_validation_note(item, state.url_validation)` and append the note. Pass `state.url_validation` into that function at call sites.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py::test_reporter_does_not_validate_urls_by_default tests/test_agents.py::test_reporter_validates_urls_when_enabled -q`

Expected: tests pass.

### Task 3: Live Preset And Documentation

**Files:**
- Modify: `src/insight_graph/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `CHANGELOG.md`
- Modify: `docs/configuration.md`
- Modify: `docs/reference-parity-roadmap.md`

- [ ] **Step 1: Write failing CLI preset test**

Find the existing live-research preset test in `tests/test_cli.py` and add an assertion that output or environment capture includes `INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=1`. If the test captures env vars, add this exact expected key/value:

```python
"INSIGHT_GRAPH_REPORTER_VALIDATE_URLS": "1"
```

- [ ] **Step 2: Run test to verify RED**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_cli.py -q`

Expected: live-research preset expectation fails.

- [ ] **Step 3: Implement preset and docs**

Add `INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=1` to the live-research preset in `src/insight_graph/cli.py`.

Document the env var in `docs/configuration.md`, add a changelog bullet, and mark Reporter URL revalidation implemented in `docs/reference-parity-roadmap.md` with snippet-level citation support as the next phase.

- [ ] **Step 4: Full verification and commit**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: pytest passes, ruff passes, whitespace check has no errors.

Commit with:

```powershell
git add CHANGELOG.md docs/configuration.md docs/reference-parity-roadmap.md src/insight_graph/agents/reporter.py src/insight_graph/cli.py src/insight_graph/report_quality/url_validation.py src/insight_graph/state.py tests/test_agents.py tests/test_cli.py tests/test_state.py tests/test_url_validation.py
git commit -m "feat(reporter): validate live reference urls"
```

- [ ] **Step 5: Merge and cleanup**

Fast-forward merge the branch into `master`, rerun full pytest, ruff, and `git diff --check`, then remove the phase worktree and branch.
