# Report Quality Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 1 of `docs/report-quality-roadmap.md` by adding deterministic report-quality metrics to Eval Bench without changing the research workflow yet.

**Architecture:** Keep the current Planner, Collector, Analyst, Critic, and Reporter behavior unchanged. Add a focused report-quality metric layer inside `src/insight_graph/eval.py`, expose metrics in JSON and Markdown eval reports, and extend summary artifacts so CI can track report quality before later phases change the chain.

**Tech Stack:** Python 3.11+, Pydantic state models, existing `insight_graph.eval` CLI, pytest, Ruff, existing CI Eval Bench artifacts.

---

## Phase Context

This plan implements **Phase 1: Report Quality Baseline** from `docs/report-quality-roadmap.md`.

This plan must not change Planner, Collector, Analyst, Critic, Reporter, tools, API, dashboard, deployment, or storage behavior. It only measures report quality. Future phases will improve the chain after these metrics exist.

## Files

- Modify: `src/insight_graph/eval.py`
  - Add deterministic report-quality metric helpers.
  - Add per-case `quality` payloads.
  - Add summary-level quality aggregates.
  - Add Markdown output for quality metrics.
- Modify: `tests/test_eval.py`
  - Add TDD coverage for quality metrics, summary aggregation, Markdown rendering, and weak-report detection.
- Modify: `scripts/summarize_eval_report.py`
  - Preserve existing summary fields and include selected report-quality summary fields.
- Modify: `tests/test_summarize_eval_report.py`
  - Add summary-script coverage for new quality fields while preserving old report compatibility.
- Modify: `docs/report-quality-roadmap.md`
  - Mark Phase 1 implementation entry points and metric names.
- Modify: `docs/demo.md`
  - Document where quality metrics appear in Eval Bench output.
- Modify: `CHANGELOG.md`
  - Add an Unreleased entry for Phase 1 report-quality baseline metrics.

## Metric Contract

Every eval case should include this new `quality` object:

```json
{
  "quality": {
    "section_count": 3,
    "required_sections_present": ["Key Findings", "Competitive Matrix", "References"],
    "missing_required_sections": [],
    "section_coverage_score": 100,
    "report_word_count": 42,
    "report_depth_score": 17,
    "unique_source_domain_count": 2,
    "unique_source_type_count": 2,
    "source_diversity_score": 67,
    "verified_evidence_count": 2,
    "unsupported_finding_count": 0,
    "unsupported_matrix_row_count": 0,
    "unsupported_claim_count": 0,
    "citation_support_score": 100,
    "duplicate_source_rate": 0
  }
}
```

Summary should include these new fields:

```json
{
  "average_section_coverage_score": 100,
  "average_report_depth_score": 17,
  "average_source_diversity_score": 67,
  "average_citation_support_score": 100,
  "total_unsupported_claims": 0,
  "average_duplicate_source_rate": 0
}
```

Scoring rules must remain backward-compatible for this phase. Do not add these metrics to `RULE_IDS` in this plan. Phase 1 measures quality; later phases may gate on it.

## Metric Definitions

Use deterministic calculations only.

```python
REQUIRED_REPORT_SECTIONS = [
    "Key Findings",
    "Competitive Matrix",
    "References",
]
```

Definitions:

- `section_count`: number of Markdown headings beginning with `## `.
- `required_sections_present`: required section names found as `## <name>` headings.
- `missing_required_sections`: required section names not found.
- `section_coverage_score`: percentage of required sections present, rounded to integer.
- `report_word_count`: count of ASCII/Unicode word-like tokens in report Markdown.
- `report_depth_score`: `min(100, round(report_word_count / 250 * 100))`. This is intentionally modest so current short deterministic reports can show partial depth without failing CI.
- `unique_source_domain_count`: number of unique domains among verified evidence.
- `unique_source_type_count`: number of unique source types among verified evidence.
- `source_diversity_score`: `min(100, round(unique_source_type_count / 3 * 100))`.
- `verified_evidence_count`: number of verified evidence items.
- `unsupported_finding_count`: findings with no evidence IDs or with evidence IDs not found in verified evidence.
- `unsupported_matrix_row_count`: matrix rows with no evidence IDs or with evidence IDs not found in verified evidence.
- `unsupported_claim_count`: sum of unsupported finding and matrix-row counts.
- `citation_support_score`: `100` when there are no findings or matrix rows; otherwise percentage of supported findings and rows.
- `duplicate_source_rate`: percentage of verified evidence items that share a source URL with another verified evidence item.

## Task 1: Add Report Quality Metric Tests

**Files:**

- Modify: `tests/test_eval.py`
- Implementation target: `src/insight_graph/eval.py`

- [ ] **Step 1: Add failing test for per-case quality metrics**

Append this test after `test_build_eval_payload_scores_case_rules` in `tests/test_eval.py`:

```python
def test_build_eval_payload_includes_report_quality_metrics(monkeypatch) -> None:
    monkeypatch.setattr(eval_module.time, "perf_counter", iter([1.0, 1.025]).__next__)

    payload = eval_module.build_eval_payload(
        [eval_module.EvalCase(query="Compare Cursor", min_references=2)],
        run_research_func=make_eval_state,
    )

    quality = payload["cases"][0]["quality"]
    assert quality["section_count"] == 3
    assert quality["required_sections_present"] == [
        "Key Findings",
        "Competitive Matrix",
        "References",
    ]
    assert quality["missing_required_sections"] == []
    assert quality["section_coverage_score"] == 100
    assert quality["report_word_count"] > 0
    assert 0 < quality["report_depth_score"] <= 100
    assert quality["unique_source_domain_count"] == 2
    assert quality["unique_source_type_count"] == 2
    assert quality["source_diversity_score"] == 67
    assert quality["verified_evidence_count"] == 2
    assert quality["unsupported_finding_count"] == 0
    assert quality["unsupported_matrix_row_count"] == 0
    assert quality["unsupported_claim_count"] == 0
    assert quality["citation_support_score"] == 100
    assert quality["duplicate_source_rate"] == 0
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_eval.py::test_build_eval_payload_includes_report_quality_metrics -v
```

Expected: FAIL with `KeyError: 'quality'`.

- [ ] **Step 3: Add failing test for weak-report quality detection**

Append this test after the previous new test:

```python
def test_report_quality_metrics_detect_unsupported_claims_and_missing_sections() -> None:
    state = GraphState(
        user_request="Weak report",
        evidence_pool=[
            Evidence(
                id="source-1",
                subtask_id="collect",
                title="Only Source",
                source_url="https://example.com/source",
                snippet="Only source evidence.",
                source_type="blog",
                verified=True,
            )
        ],
        findings=[
            Finding(
                title="Unsupported finding",
                summary="This finding points to missing evidence.",
                evidence_ids=["missing-evidence"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Example",
                positioning="No cited positioning.",
                strengths=[],
                evidence_ids=[],
            )
        ],
        critique=Critique(passed=False, reason="Weak evidence."),
        report_markdown="# Weak Report\n\n## Key Findings\n\nUnsupported claim. [1]\n",
    )

    quality = eval_module.build_report_quality_metrics(state, state.report_markdown or "")

    assert quality["missing_required_sections"] == ["Competitive Matrix", "References"]
    assert quality["section_coverage_score"] == 33
    assert quality["unsupported_finding_count"] == 1
    assert quality["unsupported_matrix_row_count"] == 1
    assert quality["unsupported_claim_count"] == 2
    assert quality["citation_support_score"] == 0
```

- [ ] **Step 4: Run the test and verify RED**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_eval.py::test_report_quality_metrics_detect_unsupported_claims_and_missing_sections -v
```

Expected: FAIL with `AttributeError: module 'insight_graph.eval' has no attribute 'build_report_quality_metrics'`.

## Task 2: Implement Report Quality Metrics

**Files:**

- Modify: `src/insight_graph/eval.py`
- Test: `tests/test_eval.py`

- [ ] **Step 1: Add constants near `RULE_IDS`**

In `src/insight_graph/eval.py`, after `RULE_IDS`, add:

```python
REQUIRED_REPORT_SECTIONS = [
    "Key Findings",
    "Competitive Matrix",
    "References",
]
SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+(.+?)\s*$")
WORD_PATTERN = re.compile(r"[\w]+", re.UNICODE)
```

- [ ] **Step 2: Add helper functions after `_score_from_rules`**

Add this code:

```python
def build_report_quality_metrics(state: GraphState, report_markdown: str) -> dict[str, Any]:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    verified_ids = {item.id for item in verified_evidence}
    headings = _section_headings(report_markdown)
    required_present = [section for section in REQUIRED_REPORT_SECTIONS if section in headings]
    missing_required = [section for section in REQUIRED_REPORT_SECTIONS if section not in headings]
    unsupported_finding_count = sum(
        1 for finding in state.findings if not _evidence_ids_supported(finding.evidence_ids, verified_ids)
    )
    unsupported_matrix_row_count = sum(
        1
        for row in state.competitive_matrix
        if not _evidence_ids_supported(row.evidence_ids, verified_ids)
    )
    claim_count = len(state.findings) + len(state.competitive_matrix)
    unsupported_claim_count = unsupported_finding_count + unsupported_matrix_row_count
    supported_claim_count = max(0, claim_count - unsupported_claim_count)
    unique_source_types = {item.source_type for item in verified_evidence}
    duplicate_source_rate = _duplicate_source_rate(verified_evidence)

    return {
        "section_count": len(headings),
        "required_sections_present": required_present,
        "missing_required_sections": missing_required,
        "section_coverage_score": _percentage(len(required_present), len(REQUIRED_REPORT_SECTIONS)),
        "report_word_count": len(WORD_PATTERN.findall(report_markdown)),
        "report_depth_score": _report_depth_score(report_markdown),
        "unique_source_domain_count": len({item.source_domain for item in verified_evidence}),
        "unique_source_type_count": len(unique_source_types),
        "source_diversity_score": min(100, round(len(unique_source_types) / 3 * 100)),
        "verified_evidence_count": len(verified_evidence),
        "unsupported_finding_count": unsupported_finding_count,
        "unsupported_matrix_row_count": unsupported_matrix_row_count,
        "unsupported_claim_count": unsupported_claim_count,
        "citation_support_score": 100 if claim_count == 0 else _percentage(supported_claim_count, claim_count),
        "duplicate_source_rate": duplicate_source_rate,
    }


def _section_headings(report_markdown: str) -> list[str]:
    return [match.group(1).strip().rstrip("#").strip() for match in SECTION_HEADING_PATTERN.finditer(report_markdown)]


def _evidence_ids_supported(evidence_ids: list[str], verified_ids: set[str]) -> bool:
    return bool(evidence_ids) and all(evidence_id in verified_ids for evidence_id in evidence_ids)


def _percentage(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 100
    return round(numerator / denominator * 100)


def _report_depth_score(report_markdown: str) -> int:
    word_count = len(WORD_PATTERN.findall(report_markdown))
    return min(100, round(word_count / 250 * 100))


def _duplicate_source_rate(evidence: list[Any]) -> int:
    if not evidence:
        return 0
    urls = [item.source_url for item in evidence]
    duplicate_count = len(urls) - len(set(urls))
    return _percentage(duplicate_count, len(urls))
```

- [ ] **Step 3: Attach quality to each case result**

In `_case_result_from_state`, after `rules = _score_rules(...)`, add:

```python
    quality = build_report_quality_metrics(state, report_markdown)
```

Then add this key to the returned dict after `report_has_competitive_matrix`:

```python
        "quality": quality,
```

- [ ] **Step 4: Add empty quality object to error cases**

In `_error_case_result`, add this key before `"error": SAFE_WORKFLOW_ERROR`:

```python
        "quality": _empty_report_quality_metrics(),
```

Add this helper after `build_report_quality_metrics`:

```python
def _empty_report_quality_metrics() -> dict[str, Any]:
    return {
        "section_count": 0,
        "required_sections_present": [],
        "missing_required_sections": list(REQUIRED_REPORT_SECTIONS),
        "section_coverage_score": 0,
        "report_word_count": 0,
        "report_depth_score": 0,
        "unique_source_domain_count": 0,
        "unique_source_type_count": 0,
        "source_diversity_score": 0,
        "verified_evidence_count": 0,
        "unsupported_finding_count": 0,
        "unsupported_matrix_row_count": 0,
        "unsupported_claim_count": 0,
        "citation_support_score": 0,
        "duplicate_source_rate": 0,
    }
```

- [ ] **Step 5: Run targeted tests and verify GREEN**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_eval.py::test_build_eval_payload_includes_report_quality_metrics tests/test_eval.py::test_report_quality_metrics_detect_unsupported_claims_and_missing_sections -v
```

Expected: both tests PASS.

## Task 3: Add Summary Quality Aggregates

**Files:**

- Modify: `tests/test_eval.py`
- Modify: `src/insight_graph/eval.py`

- [ ] **Step 1: Add failing summary aggregate test**

Append this test after `test_build_eval_payload_includes_report_quality_metrics`:

```python
def test_eval_summary_includes_report_quality_aggregates(monkeypatch) -> None:
    monkeypatch.setattr(eval_module.time, "perf_counter", iter([1.0, 1.025]).__next__)

    payload = eval_module.build_eval_payload(
        [eval_module.EvalCase(query="Compare Cursor", min_references=2)],
        run_research_func=make_eval_state,
    )

    summary = payload["summary"]
    assert summary["average_section_coverage_score"] == 100
    assert summary["average_report_depth_score"] == payload["cases"][0]["quality"]["report_depth_score"]
    assert summary["average_source_diversity_score"] == 67
    assert summary["average_citation_support_score"] == 100
    assert summary["total_unsupported_claims"] == 0
    assert summary["average_duplicate_source_rate"] == 0
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_eval.py::test_eval_summary_includes_report_quality_aggregates -v
```

Expected: FAIL with `KeyError: 'average_section_coverage_score'`.

- [ ] **Step 3: Add aggregate helpers in `src/insight_graph/eval.py`**

Add this helper after `_failed_rule_counts`:

```python
def _average_quality(case_results: list[dict[str, Any]], key: str) -> int:
    if not case_results:
        return 0
    return round(
        sum(int(item.get("quality", {}).get(key, 0)) for item in case_results) / len(case_results)
    )
```

In `_build_summary`, add these fields to the returned dict after `total_llm_calls`:

```python
        "average_section_coverage_score": _average_quality(
            case_results, "section_coverage_score"
        ),
        "average_report_depth_score": _average_quality(case_results, "report_depth_score"),
        "average_source_diversity_score": _average_quality(
            case_results, "source_diversity_score"
        ),
        "average_citation_support_score": _average_quality(
            case_results, "citation_support_score"
        ),
        "total_unsupported_claims": sum(
            int(item.get("quality", {}).get("unsupported_claim_count", 0))
            for item in case_results
        ),
        "average_duplicate_source_rate": _average_quality(case_results, "duplicate_source_rate"),
```

- [ ] **Step 4: Run summary test and verify GREEN**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_eval.py::test_eval_summary_includes_report_quality_aggregates -v
```

Expected: PASS.

## Task 4: Render Quality Metrics in Eval Markdown

**Files:**

- Modify: `tests/test_eval.py`
- Modify: `src/insight_graph/eval.py`

- [ ] **Step 1: Update Markdown test payload**

In `test_format_markdown_includes_eval_score_columns`, add this `quality` object inside the case payload:

```python
                "quality": {
                    "section_count": 3,
                    "required_sections_present": [
                        "Key Findings",
                        "Competitive Matrix",
                        "References",
                    ],
                    "missing_required_sections": [],
                    "section_coverage_score": 100,
                    "report_word_count": 42,
                    "report_depth_score": 17,
                    "unique_source_domain_count": 2,
                    "unique_source_type_count": 2,
                    "source_diversity_score": 67,
                    "verified_evidence_count": 2,
                    "unsupported_finding_count": 0,
                    "unsupported_matrix_row_count": 0,
                    "unsupported_claim_count": 0,
                    "citation_support_score": 100,
                    "duplicate_source_rate": 0,
                },
```

Add these summary fields to the summary payload:

```python
            "average_section_coverage_score": 100,
            "average_report_depth_score": 17,
            "average_source_diversity_score": 67,
            "average_citation_support_score": 100,
            "total_unsupported_claims": 0,
            "average_duplicate_source_rate": 0,
```

Add these assertions after existing Markdown assertions:

```python
    assert "## Report Quality" in markdown
    assert "| Query | Section coverage | Report depth | Source diversity | Citation support | Unsupported claims | Duplicate source rate |" in markdown
    assert "| Compare Cursor | 100 | 17 | 67 | 100 | 0 | 0 |" in markdown
    assert "## Report Quality Summary" in markdown
    assert "| Avg section coverage | Avg report depth | Avg source diversity | Avg citation support | Unsupported claims | Avg duplicate source rate |" in markdown
```

- [ ] **Step 2: Run Markdown test and verify RED**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_eval.py::test_format_markdown_includes_eval_score_columns -v
```

Expected: FAIL because `## Report Quality` is missing.

- [ ] **Step 3: Add quality Markdown rendering**

In `format_markdown`, after the first case table loop and before `summary = payload["summary"]`, insert:

```python
    lines.extend(
        [
            "",
            "## Report Quality",
            "",
            "| Query | Section coverage | Report depth | Source diversity | Citation support | Unsupported claims | Duplicate source rate |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in payload["cases"]:
        quality = item.get("quality", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(str(item["query"])),
                    str(quality.get("section_coverage_score", 0)),
                    str(quality.get("report_depth_score", 0)),
                    str(quality.get("source_diversity_score", 0)),
                    str(quality.get("citation_support_score", 0)),
                    str(quality.get("unsupported_claim_count", 0)),
                    str(quality.get("duplicate_source_rate", 0)),
                ]
            )
            + " |"
        )
```

In the Summary section, after the existing summary table block, add:

```python
    lines.extend(
        [
            "",
            "## Report Quality Summary",
            "",
            "| Avg section coverage | Avg report depth | Avg source diversity | Avg citation support | Unsupported claims | Avg duplicate source rate |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
            "| "
            + " | ".join(
                [
                    str(summary.get("average_section_coverage_score", 0)),
                    str(summary.get("average_report_depth_score", 0)),
                    str(summary.get("average_source_diversity_score", 0)),
                    str(summary.get("average_citation_support_score", 0)),
                    str(summary.get("total_unsupported_claims", 0)),
                    str(summary.get("average_duplicate_source_rate", 0)),
                ]
            )
            + " |",
        ]
    )
```

- [ ] **Step 4: Run Markdown test and verify GREEN**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_eval.py::test_format_markdown_includes_eval_score_columns -v
```

Expected: PASS.

## Task 5: Extend Eval Summary Script

**Files:**

- Modify: `scripts/summarize_eval_report.py`
- Modify: `tests/test_summarize_eval_report.py`

- [ ] **Step 1: Add failing summary extraction test**

In `tests/test_summarize_eval_report.py`, update `EVAL_PAYLOAD["summary"]` with:

```python
        "average_section_coverage_score": 100,
        "average_report_depth_score": 17,
        "average_source_diversity_score": 67,
        "average_citation_support_score": 100,
        "total_unsupported_claims": 0,
        "average_duplicate_source_rate": 0,
```

Update expected dictionaries in `test_summarize_eval_report_extracts_summary_subset` and `test_main_reads_eval_report_and_prints_json` to include the same six fields.

Update `test_format_markdown_outputs_compact_summary_table` with:

```python
    assert "## Report Quality" in markdown
    assert "| 100 | 17 | 67 | 100 | 0 | 0 |" in markdown
```

Append this compatibility test:

```python
def test_summarize_eval_report_defaults_missing_quality_fields() -> None:
    payload = {
        "summary": {
            "case_count": 1,
            "average_score": 80,
            "passed_count": 1,
            "failed_count": 0,
            "failed_rules": {},
            "total_duration_ms": 10,
        }
    }

    summary = summary_module.summarize_eval_report(payload)

    assert summary["average_section_coverage_score"] == 0
    assert summary["average_report_depth_score"] == 0
    assert summary["average_source_diversity_score"] == 0
    assert summary["average_citation_support_score"] == 0
    assert summary["total_unsupported_claims"] == 0
    assert summary["average_duplicate_source_rate"] == 0
```

- [ ] **Step 2: Run summary tests and verify RED**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_summarize_eval_report.py -v
```

Expected: FAIL because the summary script does not include quality fields or Markdown section.

- [ ] **Step 3: Add quality summary fields with defaults**

In `scripts/summarize_eval_report.py`, add this constant after `SUMMARY_FIELDS`:

```python
QUALITY_SUMMARY_FIELDS = [
    "average_section_coverage_score",
    "average_report_depth_score",
    "average_source_diversity_score",
    "average_citation_support_score",
    "total_unsupported_claims",
    "average_duplicate_source_rate",
]
```

Then update `summarize_eval_report()` after the `failed_rules` type check:

```python
    for field in QUALITY_SUMMARY_FIELDS:
        result[field] = summary.get(field, 0)
```

This keeps old eval reports readable while new reports expose quality summary fields.

- [ ] **Step 4: Update summary Markdown output**

In `format_markdown`, after the initial summary table, add:

```python
    lines.extend(
        [
            "",
            "## Report Quality",
            "",
            "| Avg section coverage | Avg report depth | Avg source diversity | Avg citation support | Unsupported claims | Avg duplicate source rate |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
            (
                f"| {summary['average_section_coverage_score']} | "
                f"{summary['average_report_depth_score']} | "
                f"{summary['average_source_diversity_score']} | "
                f"{summary['average_citation_support_score']} | "
                f"{summary['total_unsupported_claims']} | "
                f"{summary['average_duplicate_source_rate']} |"
            ),
        ]
    )
```

- [ ] **Step 5: Run summary tests and verify GREEN**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_summarize_eval_report.py -v
```

Expected: all tests PASS.

## Task 6: Update Documentation

**Files:**

- Modify: `docs/report-quality-roadmap.md`
- Modify: `docs/demo.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update `docs/report-quality-roadmap.md` Phase 1**

Under `### Phase 1: Report Quality Baseline`, add this paragraph after the Goal line:

```markdown
Initial implementation adds deterministic Eval Bench metrics: section coverage, report depth, source diversity, citation support, unsupported claim count, and duplicate source rate. These metrics are measured first and are not yet hard gates in `RULE_IDS`.
```

- [ ] **Step 2: Update `docs/demo.md` Eval Bench section**

After the paragraph ending with `without using an LLM judge.`, add:

```markdown
Report-quality metrics also appear in Eval Bench JSON and Markdown reports. They track section coverage, report depth, source diversity, citation support, unsupported claims, and duplicate source rate. These metrics are deterministic and offline by default.
```

- [ ] **Step 3: Update `CHANGELOG.md`**

Under `## Unreleased`, add:

```markdown
- Added deterministic report-quality metrics to Eval Bench outputs.
```

- [ ] **Step 4: Run diff check**

Run:

```bash
git diff --check
```

Expected: no whitespace errors. CRLF warnings on Windows are acceptable.

## Task 7: Verification

**Files:**

- No additional files.

- [ ] **Step 1: Run targeted eval tests**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_eval.py tests/test_summarize_eval_report.py -v
```

Expected: all selected tests PASS.

- [ ] **Step 2: Run Eval Bench locally**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m insight_graph.eval --case-file docs/evals/default.json --output reports/eval.json
```

Expected: exit code `0`; `reports/eval.json` contains `quality` under each case and `average_section_coverage_score` in `summary`.

- [ ] **Step 3: Generate Markdown Eval report locally**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m insight_graph.eval --case-file docs/evals/default.json --markdown --output reports/eval.md
```

Expected: exit code `0`; `reports/eval.md` contains `## Report Quality` and `## Report Quality Summary`.

- [ ] **Step 4: Run full tests**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
```

Expected: full suite PASS.

- [ ] **Step 5: Run full Ruff**

Run:

```bash
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 6: Run diff check**

Run:

```bash
git diff --check
```

Expected: no whitespace errors. CRLF warnings are acceptable on this workspace.

## Task 8: Release Handoff

**Files:**

- Modify: `CHANGELOG.md`

- [ ] **Step 1: Review git status and diff**

Run:

```bash
git status --short --branch
git diff --stat
```

Expected: only files from this plan are modified, plus existing approved roadmap docs if still uncommitted.

- [ ] **Step 2: Ask before committing**

Because this environment requires explicit user approval before commits, ask the user before running `git commit`.

Suggested commit message after approval:

```bash
git add src/insight_graph/eval.py tests/test_eval.py scripts/summarize_eval_report.py tests/test_summarize_eval_report.py docs/report-quality-roadmap.md docs/demo.md CHANGELOG.md
git commit -m "feat(eval): add report quality metrics"
```

- [ ] **Step 3: Push and release only after approval**

If the user approves push and release, follow existing repository release practice:

```bash
git push origin master
gh run list --branch master --limit 3
gh run watch <run-id> --exit-status
```

After CI passes, update changelog for the next release tag and create a GitHub release.

## Self-Review Notes

- Spec coverage: This plan implements Phase 1 only: rubric metrics, Eval Bench JSON/Markdown output, summary artifact support, docs, and verification.
- Route compliance: This plan does not change Planner, Collector, Analyst, Critic, Reporter, API, dashboard, deployment, storage, or live provider behavior.
- Determinism: All metrics use existing `GraphState` and Markdown text; no network or LLM judge is introduced.
- Backward compatibility: Existing top-level eval fields remain unchanged. New fields are additive.
- Next phase after completion: Phase 2: Domain Profile v1.
