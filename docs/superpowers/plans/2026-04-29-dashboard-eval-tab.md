# Dashboard Eval Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a static dashboard Eval tab that explains where to find and how to use CI Eval Bench artifacts.

**Architecture:** Reuse the existing static dashboard HTML and tab rendering in `src/insight_graph/dashboard.py`. Add one tab button and one render branch that returns static safe HTML; no new API calls or state are required.

**Tech Stack:** Static HTML/CSS/vanilla JavaScript dashboard, pytest HTML marker assertions, Ruff.

---

## File Structure

- Modify `tests/test_api.py`: add dashboard Eval tab marker assertions.
- Modify `src/insight_graph/dashboard.py`: add Eval tab and static panel rendering.
- Modify `README.md`: mention the Dashboard Eval tab.
- Modify `docs/demo.md`: mention the Dashboard Eval tab.
- Modify `CHANGELOG.md`: add Unreleased entry.
- Create spec/plan files under `docs/superpowers/`.

## Task 1: Failing Test

- [ ] Extend `tests/test_api.py::test_dashboard_returns_html` with assertions for:

```python
    assert 'data-tab="eval"' in response.text
    assert "Eval Ops" in response.text
    assert "reports/eval-summary.md" in response.text
    assert "reports/eval-history.md" in response.text
    assert "Dashboard does not fetch GitHub Actions artifacts" in response.text
```

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py::test_dashboard_returns_html -v`.
- [ ] Confirm it fails because `data-tab="eval"` is not in dashboard HTML.

## Task 2: Dashboard Tab

- [ ] Add `<button class="tab" data-tab="eval" type="button">Eval</button>` before Raw JSON.
- [ ] Add a `renderEvalOps()` function returning static HTML with eval artifact paths and commands.
- [ ] Add `if (state.activeTab === 'eval') els.reportPanel.innerHTML = renderEvalOps();` in `renderDetail()`.
- [ ] Run targeted dashboard test and confirm it passes.

## Task 3: Docs

- [ ] Update `README.md` dashboard paragraph to mention the Eval tab.
- [ ] Update `docs/demo.md` Eval Bench section to mention the dashboard Eval tab.
- [ ] Update `CHANGELOG.md` Unreleased with `Added Dashboard Eval artifact guidance tab.`

## Task 4: Verification

- [ ] Run targeted dashboard test.
- [ ] Run full `pytest`.
- [ ] Run `ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: tab, static content, tests, docs, changelog, and no GitHub API integration are covered.
- Placeholder scan: no placeholders.
- Type consistency: artifact file names match CI output.
