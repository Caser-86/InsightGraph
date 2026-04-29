# Dashboard Eval Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a static Eval Gate visibility card to the dashboard Overview tab.

**Architecture:** Reuse the existing static dashboard HTML in `src/insight_graph/dashboard.py`. The card is rendered in `renderOverview()` as another `.info-card`, so no new API, state, or JavaScript data flow is needed.

**Tech Stack:** FastAPI static HTML response, vanilla JavaScript template strings, pytest, Ruff.

---

## File Structure

- Modify `tests/test_api.py`: assert dashboard HTML contains Eval Gate markers.
- Modify `src/insight_graph/dashboard.py`: add the static Overview card.
- Modify `README.md`: mention Dashboard shows Eval Gate metadata.
- Modify `docs/demo.md`: mention Dashboard Overview Eval Gate card.
- Modify `CHANGELOG.md`: add Unreleased entry.

## Task 1: Failing Test

- [ ] Add assertions to `tests/test_api.py::test_dashboard_returns_html`:

```python
    assert "Eval Gate" in response.text
    assert "docs/evals/default.json" in response.text
    assert "--min-score 85 --fail-on-case-failure" in response.text
    assert "eval-reports" in response.text
    assert "reports/eval.json" in response.text
    assert "reports/eval.md" in response.text
```

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py::test_dashboard_returns_html -v`.
- [ ] Confirm the test fails because `Eval Gate` is not in the dashboard HTML.

## Task 2: Dashboard Card

- [ ] In `src/insight_graph/dashboard.py`, add this `.info-card` to the `renderOverview()` grid after the existing `Critic` card and before `Error`:

```html
<div class="info-card"><span>Eval Gate</span><strong>docs/evals/default.json<br>--min-score 85 --fail-on-case-failure<br>CI artifact: eval-reports<br>Reports: reports/eval.json, reports/eval.md</strong></div>
```

- [ ] Run the targeted dashboard test again and confirm it passes.

## Task 3: Docs

- [ ] Update `README.md` dashboard paragraph to mention the Overview tab shows Eval Gate metadata.
- [ ] Update `docs/demo.md` Eval Bench section to mention the Dashboard Overview Eval Gate card.
- [ ] Update `CHANGELOG.md` Unreleased with `Added Dashboard Eval Gate visibility.`

## Task 4: Verification

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py::test_dashboard_returns_html -v`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: dashboard card, tests, docs, changelog, and verification are covered.
- Placeholder scan: no placeholders.
- Type consistency: all marker strings match the dashboard card content.
