# Remaining Product Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining InsightGraph improvements in strict order so the product moves from live research MVP toward a reliable networked deep-research agent.

**Architecture:** Work in independent git worktrees, one batch at a time. Each batch is TDD-first, produces one or more focused commits, then merges back to `master` only after full `pytest`, full `ruff`, and `git diff --check`. Offline tests must fake network/LLM/database calls.

**Tech Stack:** Python 3.11+, LangGraph, Pydantic, FastAPI, Typer, pytest, ruff, stdlib HTTP/URL tooling, optional PostgreSQL/pgvector behind existing adapters.

---

## Current Baseline

Latest completed commits on `master`:

- `fa12af8 feat: retain search fetch telemetry`
- `ef77f61 fix: harden live HTTP fetching`
- `06d2665 feat: promote live research to LLM workflow`

Already complete:

- `live-research` now means networked search plus LLM Analyst/Reporter.
- API and CLI presets are aligned.
- live `web_search` no longer falls back to `mock_search`.
- Critic requires `support_status == supported`.
- Reporter renders `support_status` / `unsupported_reason` correctly.
- HTTP fetch blocks localhost/private/link-local/metadata IPs, validates redirect target, allows only HTML/text/PDF-like content types, and reads with a bounded streaming limit.
- Search/pre-fetch evidence retains provider/rank/query/search snippet metadata.
- Empty/failed pre-fetch creates unverified diagnostic evidence with `fetch_status` / `fetch_error`.

## Global Rules For Every Batch

1. Create a worktree before edits:

```powershell
git worktree add ".worktrees\<batch-name>" -b <batch-name>
```

2. Start with focused baseline tests for the files being touched:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest <focused tests> -q
```

3. Write RED tests before implementation.

4. After each task passes focused tests, commit inside the worktree.

5. Before merge, run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

6. Merge to `master`, rerun the same three verification commands on `master`, then remove the worktree and branch.

7. Update `C:\Users\77670\Desktop\InsightGraph完整改进优先级表.md` after each merged batch.

---

## Batch 1: Finish Fetch Reliability And Source Semantics

**Goal:** Complete P1 Phase 2: canonical URLs, source typing v2, verification-state metadata, and basic retry/backoff/error taxonomy.

**Why First:** This is the evidence foundation. Planner/Reporter improvements are less useful if the source layer cannot deduplicate, classify, or explain source reliability.

### Task 1.1: Canonical URL Normalization And Deduplication

**Files:**

- Create: `src/insight_graph/tools/url_canonicalization.py`
- Test: `tests/test_url_canonicalization.py`
- Modify: `src/insight_graph/tools/pre_fetch.py`
- Modify: `src/insight_graph/agents/executor.py`

**Behavior:**

- Normalize scheme and host to lowercase.
- Remove URL fragments.
- Drop known tracking params: `utm_*`, `fbclid`, `gclid`, `msclkid`.
- Preserve meaningful query params sorted by key/value.
- Remove default ports `:80` for HTTP and `:443` for HTTPS.
- Deduplicate pre-fetch candidates by canonical URL before fetch.
- Deduplicate final evidence by canonical source URL when available, falling back to current `(id, source_url)` behavior.

**RED tests:**

- `tests/test_url_canonicalization.py::test_canonicalize_url_removes_tracking_and_fragment`
- `tests/test_url_canonicalization.py::test_canonicalize_url_preserves_meaningful_sorted_query`
- `tests/test_pre_fetch.py::test_pre_fetch_deduplicates_candidates_by_canonical_url`
- `tests/test_executor.py::test_executor_deduplicates_evidence_by_canonical_url`

**Implementation notes:**

- Add optional `canonical_url: str | None = None` to `Evidence` in `src/insight_graph/state.py` only if needed for final evidence dedupe. If adding it, add `tests/test_state.py::test_evidence_stores_canonical_url`.
- In `pre_fetch_results`, calculate canonical URL for each `SearchResult.url`; skip later candidates with the same canonical URL.
- When attaching search metadata, set `canonical_url` on evidence if the field is added.

**Verification:**

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_url_canonicalization.py tests/test_pre_fetch.py tests/test_executor.py tests/test_state.py -q
```

**Commit:**

```powershell
git add src/insight_graph/tools/url_canonicalization.py src/insight_graph/tools/pre_fetch.py src/insight_graph/agents/executor.py src/insight_graph/state.py tests/test_url_canonicalization.py tests/test_pre_fetch.py tests/test_executor.py tests/test_state.py
git commit -m "feat: canonicalize fetched source URLs"
```

### Task 1.2: Source Type v2

**Files:**

- Create: `src/insight_graph/report_quality/source_types.py`
- Test: `tests/test_source_types.py`
- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/tools/fetch_url.py`
- Modify: `src/insight_graph/report_quality/evidence_scoring.py`

**Behavior:**

- Expand `SourceType` to include at least: `official_site`, `docs`, `github`, `news`, `blog`, `sec`, `paper`, `unknown`.
- Classify SEC domains and SEC filing paths as `sec`.
- Classify docs subdomains and `/docs`, `/documentation`, `.pdf` paths as `docs` unless SEC-specific.
- Classify GitHub domains as `github`.
- Classify known news domains as `news`.
- Classify common blog paths/subdomains as `blog`.
- Keep unknown as fallback.
- Update evidence scoring authority map for new types.

**RED tests:**

- `tests/test_source_types.py::test_infer_source_type_detects_sec_sources`
- `tests/test_source_types.py::test_infer_source_type_detects_news_and_blog_sources`
- `tests/test_fetch_url.py::test_fetch_url_uses_source_type_classifier`
- `tests/test_evidence_scoring.py::test_score_evidence_prioritizes_sec_and_official_sources`

**Implementation notes:**

- Move `fetch_url.infer_source_type()` implementation to `report_quality/source_types.py` and leave a thin import wrapper in `fetch_url.py` if existing tests import it.
- Keep classification deterministic and domain-list based; do not fetch external reputation data.

**Verification:**

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_source_types.py tests/test_fetch_url.py tests/test_evidence_scoring.py -q
```

**Commit:**

```powershell
git add src/insight_graph/report_quality/source_types.py src/insight_graph/tools/fetch_url.py src/insight_graph/report_quality/evidence_scoring.py src/insight_graph/state.py tests/test_source_types.py tests/test_fetch_url.py tests/test_evidence_scoring.py
git commit -m "feat: classify live source types"
```

### Task 1.3: Verification State Metadata

**Files:**

- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/tools/fetch_url.py`
- Modify: `src/insight_graph/tools/pre_fetch.py`
- Modify: `src/insight_graph/report_quality/citation_support.py`
- Test: `tests/test_state.py`
- Test: `tests/test_fetch_url.py`
- Test: `tests/test_pre_fetch.py`
- Test: `tests/test_citation_support.py`

**Behavior:**

- Add these optional Evidence fields:
  - `reachable: bool | None`
  - `source_trusted: bool | None`
  - `claim_supported: bool | None`
- For successful `fetch_url` evidence: `reachable=True`, `source_trusted=True` when source type is not `unknown` or when source type is `official_site/docs/github/news/sec/paper`, `claim_supported=None`.
- For diagnostic pre-fetch evidence: `reachable=False` for failed fetch, `reachable=True` for empty fetch if the fetch returned no evidence without an exception, `source_trusted` based on candidate URL classification when possible, `claim_supported=False`.
- Citation support validator should set `claim_supported=True` only through its output records, not mutate Evidence in this batch.

**RED tests:**

- `tests/test_state.py::test_evidence_stores_verification_state_metadata`
- `tests/test_fetch_url.py::test_fetch_url_marks_successful_evidence_reachable`
- `tests/test_pre_fetch.py::test_pre_fetch_marks_diagnostic_evidence_verification_state`
- `tests/test_citation_support.py::test_validate_citation_support_reports_claim_support_without_mutating_evidence`

**Implementation notes:**

- Keep `verified` for backward compatibility.
- Do not change Reporter reference filtering yet; it still uses `verified`.
- This batch adds metadata only, minimizing behavioral risk.

**Verification:**

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_state.py tests/test_fetch_url.py tests/test_pre_fetch.py tests/test_citation_support.py -q
```

**Commit:**

```powershell
git add src/insight_graph/state.py src/insight_graph/tools/fetch_url.py src/insight_graph/tools/pre_fetch.py src/insight_graph/report_quality/citation_support.py tests/test_state.py tests/test_fetch_url.py tests/test_pre_fetch.py tests/test_citation_support.py
git commit -m "feat: add evidence verification metadata"
```

### Task 1.4: Retry/Backoff And Error Taxonomy

**Files:**

- Modify: `src/insight_graph/tools/http_client.py`
- Modify: `src/insight_graph/tools/pre_fetch.py`
- Test: `tests/test_http_client.py`
- Test: `tests/test_pre_fetch.py`

**Behavior:**

- Add `FetchError.kind` with values like `blocked_url`, `dns`, `network`, `http_status`, `content_type`, `too_large`, `empty`, `decode`, `unknown`.
- Add `fetch_text(..., retries: int = 0, backoff_seconds: float = 0.0, sleep_func: Callable[[float], None] | None = None)`.
- Retry only transient network errors and 5xx HTTP errors.
- Do not retry blocked URL, unsupported scheme, disallowed content type, oversized response, or 4xx.
- Diagnostic evidence `fetch_error` should include a stable kind prefix, e.g. `network: connection refused`.

**RED tests:**

- `tests/test_http_client.py::test_fetch_text_tags_blocked_url_errors`
- `tests/test_http_client.py::test_fetch_text_retries_transient_network_error`
- `tests/test_http_client.py::test_fetch_text_does_not_retry_blocked_url`
- `tests/test_pre_fetch.py::test_pre_fetch_diagnostic_error_includes_fetch_error_kind`

**Implementation notes:**

- Keep exception message compatible where current tests match text.
- If changing `FetchError` constructor, preserve `str(exc)`.
- Do not add global rate limiting yet; keep scope to retry/backoff and classification.

**Verification:**

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_http_client.py tests/test_pre_fetch.py -q
```

**Commit:**

```powershell
git add src/insight_graph/tools/http_client.py src/insight_graph/tools/pre_fetch.py tests/test_http_client.py tests/test_pre_fetch.py
git commit -m "feat: classify and retry fetch errors"
```

### Batch 1 Final Verification And Merge

Run full verification in the worktree and on `master` after merge:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Update docs:

- `README.md`: source metadata / verification metadata wording.
- `docs/configuration.md`: fetch retry/error taxonomy and canonical URL behavior.
- `C:\Users\77670\Desktop\InsightGraph完整改进优先级表.md`: mark canonical URL, source typing, evidence model, retry/error taxonomy as done or partial.

---

## Batch 2: QueryStrategy Planner v2

**Goal:** Replace fixed collection query behavior with a structured section/entity/source-aware query strategy model.

**Why Second:** Once source quality metadata is stronger, Planner can intentionally request missing source classes and section-specific evidence.

### Task 2.1: Add QueryStrategy State Model

**Files:**

- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/agents/planner.py`
- Test: `tests/test_state.py`
- Test: `tests/test_agents.py`

**Behavior:**

- Add `query_strategies: list[dict[str, object]] = Field(default_factory=list)` to `GraphState`.
- Planner populates strategies after section plan is built.
- Each strategy has:
  - `strategy_id`
  - `section_id`
  - `tool_name`
  - `query`
  - `source_type`
  - `entity_names`
  - `round`
  - `reason`

**RED tests:**

- `tests/test_state.py::test_graph_state_starts_with_empty_query_strategies`
- `tests/test_agents.py::test_planner_builds_query_strategies_for_section_sources`

**Implementation notes:**

- Keep strategies as dictionaries for low-risk compatibility.
- Do not create new Pydantic model unless needed.

### Task 2.2: Entity And Domain-Aware Strategy Expansion

**Files:**

- Modify: `src/insight_graph/agents/planner.py`
- Modify: `src/insight_graph/report_quality/entity_resolver.py` only if needed
- Test: `tests/test_agents.py`

**Behavior:**

- Strategy query should include entity names and aliases when available.
- Strategy query should include official domains when entity resolver provides them.
- Domain profile source requirements should drive tool/source type pairings.

**RED tests:**

- `tests/test_agents.py::test_planner_query_strategy_includes_entity_aliases`
- `tests/test_agents.py::test_planner_query_strategy_uses_required_source_types`

### Task 2.3: Replan Strategy Generation From Critic Requests

**Files:**

- Modify: `src/insight_graph/agents/planner.py`
- Modify: `src/insight_graph/agents/critic.py` only if strategy keys need more detail
- Test: `tests/test_agents.py`

**Behavior:**

- On retry (`state.iterations > 0`), Planner consumes `replan_requests` to add follow-up strategies.
- Follow-up query includes missing section ID, missing source types, missing evidence count, and unsupported claim text when available.
- Query strategy IDs must differ from first-round strategy IDs.

**RED tests:**

- `tests/test_agents.py::test_planner_replan_strategy_uses_missing_source_types`
- `tests/test_agents.py::test_planner_replan_strategy_uses_unsupported_claim`

### Batch 2 Verification

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py tests/test_state.py -q
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

---

## Batch 3: Executor v2 Strategy Execution And Collection Telemetry

**Goal:** Make Executor consume `query_strategies`, record per-query/per-url telemetry, and expose clearer stop reasons.

### Task 3.1: Execute QueryStrategy Records

**Files:**

- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_executor.py`

**Behavior:**

- If `state.query_strategies` is non-empty, Executor uses strategies rather than generating one query from `_collection_query()`.
- Each strategy dispatches its `tool_name` and `query`.
- Tool call records include `strategy_id` if adding optional `strategy_id: str | None` to `ToolCallRecord`.

**RED tests:**

- `tests/test_executor.py::test_executor_runs_query_strategies_when_present`
- `tests/test_executor.py::test_executor_tool_log_records_strategy_id`

### Task 3.2: Per-URL Candidate Telemetry In Collection Rounds

**Files:**

- Modify: `src/insight_graph/agents/executor.py`
- Modify: `src/insight_graph/state.py` only if adding `source_candidates` or `collection_events`
- Test: `tests/test_executor.py`

**Behavior:**

- Round summaries include:
  - `query_strategy_count`
  - `failed_fetch_count`
  - `empty_fetch_count`
  - `verified_evidence_count`
- Counts derive from evidence `fetch_status` and `verified`.

**RED tests:**

- `tests/test_executor.py::test_executor_round_summary_counts_fetch_diagnostics`

### Task 3.3: Clear Stop Reasons

**Files:**

- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_executor.py`

**Behavior:**

- Stop reasons include existing reasons plus:
  - `network_failed`
  - `no_verified_evidence`
  - `query_strategy_exhausted`
- Preserve existing tests for `sufficient`, `no_new_evidence`, `tool_budget_exhausted`.

**RED tests:**

- `tests/test_executor.py::test_executor_uses_network_failed_stop_reason_when_all_fetches_fail`
- `tests/test_executor.py::test_executor_uses_query_strategy_exhausted_stop_reason`

### Batch 3 Verification

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_executor.py tests/test_agents.py tests/test_state.py -q
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

---

## Batch 4: Relevance Audit And Budget Clarity

**Goal:** Make evidence filtering auditable and budget failures explicit.

### Task 4.1: Evidence Relevance Metadata

**Files:**

- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/agents/relevance.py`
- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_relevance.py`
- Test: `tests/test_executor.py`

**Behavior:**

- Add optional Evidence fields:
  - `relevance_status: Literal["kept", "dropped"] | None`
  - `relevance_reason: str | None`
- `filter_relevant_evidence()` returns kept evidence with `relevance_status="kept"` and dropped count as today.
- If storing dropped evidence is too disruptive, keep dropped evidence out of `evidence_pool` but record counts/reasons in tool call log or round summary.

**RED tests:**

- `tests/test_relevance.py::test_relevance_filter_marks_kept_evidence_reason`
- `tests/test_executor.py::test_executor_records_relevance_drop_reason_summary`

### Task 4.2: Token Budget Exhaustion Records

**Files:**

- Modify: `src/insight_graph/agents/relevance.py`
- Modify: `src/insight_graph/agents/analyst.py`
- Modify: `src/insight_graph/agents/reporter.py`
- Test: `tests/test_relevance.py`
- Test: `tests/test_agents.py`

**Behavior:**

- When LLM relevance/Analyst/Reporter cannot start due to token budget, append a sanitized `LLMCallRecord` with `success=False` and `error="budget_exhausted"`.
- Do not call external LLM.

**RED tests:**

- `tests/test_relevance.py::test_openai_relevance_records_budget_exhaustion`
- `tests/test_agents.py::test_analyst_records_budget_exhaustion`
- `tests/test_agents.py::test_reporter_records_budget_exhaustion`

---

## Batch 5: Citation Validator v2

**Goal:** Upgrade citation support from binary lexical matching to supported/partial/unsupported with snippet-level evidence.

### Task 5.1: Partial Support Status

**Files:**

- Modify: `src/insight_graph/report_quality/citation_support.py`
- Modify: `src/insight_graph/agents/critic.py`
- Modify: `src/insight_graph/agents/reporter.py`
- Test: `tests/test_citation_support.py`
- Test: `tests/test_agents.py`

**Behavior:**

- Add `partial` status when `support_score` is between a low threshold and full support threshold.
- Critic should fail on both `partial` and `unsupported`.
- Reporter renders partial status and reason.

**RED tests:**

- `tests/test_citation_support.py::test_validate_citation_support_marks_partial_claim`
- `tests/test_agents.py::test_critic_rejects_partial_citation_support`

### Task 5.2: Evidence Snippet Matching Improvements

**Files:**

- Modify: `src/insight_graph/report_quality/citation_support.py`
- Test: `tests/test_citation_support.py`

**Behavior:**

- Normalize punctuation, plural suffixes, hyphenated words, and case more robustly.
- Keep deterministic behavior.
- Output top supporting snippets sorted by term overlap.

**RED tests:**

- `tests/test_citation_support.py::test_validate_citation_support_normalizes_hyphenated_terms`
- `tests/test_citation_support.py::test_validate_citation_support_sorts_snippets_by_overlap`

### Task 5.3: Optional LLM Citation Judge Boundary

**Files:**

- Create: `src/insight_graph/report_quality/llm_citation_judge.py`
- Test: `tests/test_llm_citation_judge.py`
- Modify: `src/insight_graph/report_quality/citation_support.py`

**Behavior:**

- Add opt-in `INSIGHT_GRAPH_CITATION_JUDGE=openai_compatible`.
- Default remains deterministic.
- Tests use fake client; no live network.

---

## Batch 6: Analyst v2 Grounded Claims And Competitive Matrix v2

**Goal:** Improve analysis depth while keeping all claims evidence-bound.

### Task 6.1: Grounded Claim Shape

**Files:**

- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/agents/analyst.py`
- Test: `tests/test_state.py`
- Test: `tests/test_agents.py`

**Behavior:**

- Add `grounded_claims: list[dict[str, object]] = Field(default_factory=list)` to `GraphState`.
- Each claim includes `claim`, `section_id`, `evidence_ids`, `confidence`, `risk`, `unknowns`.
- Deterministic Analyst populates claims from verified findings.

### Task 6.2: Competitive Matrix v2 Fields

**Files:**

- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/agents/analyst.py`
- Modify: `src/insight_graph/agents/reporter.py`
- Test: `tests/test_agents.py`

**Behavior:**

- Add optional fields to `CompetitiveMatrixRow`:
  - `pricing`
  - `features`
  - `integrations`
  - `target_users`
  - `risks`
- Reporter renders available fields without breaking older rows.

### Task 6.3: Analyst Prompt v2

**Files:**

- Modify: `src/insight_graph/agents/analyst.py`
- Test: `tests/test_agents.py`

**Behavior:**

- LLM Analyst prompt requests grounded claims and richer matrix fields.
- Parser rejects any new fields whose evidence IDs are not verified.

---

## Batch 7: Reporter v2 Long-Form Report

**Goal:** Generate a more complete report structure using only approved claims and verified evidence.

### Task 7.1: Approved Claims Input Boundary

**Files:**

- Modify: `src/insight_graph/agents/reporter.py`
- Test: `tests/test_agents.py`

**Behavior:**

- Reporter only includes findings/grounded claims whose citation support is `supported`.
- Unsupported/partial claims appear only in Citation Support, not in main report body.

### Task 7.2: Standard Long-Form Sections

**Files:**

- Modify: `src/insight_graph/agents/reporter.py`
- Test: `tests/test_agents.py`

**Behavior:**

- Report sections: Executive Summary, Background, Analysis, Competitive Landscape, Risks, Outlook, Citation Support, References.
- If a section has no supported evidence, it says evidence is insufficient rather than inventing content.

### Task 7.3: LLM Reporter v2 Prompt And Validation

**Files:**

- Modify: `src/insight_graph/agents/reporter.py`
- Test: `tests/test_agents.py`

**Behavior:**

- LLM prompt receives only approved claims and verified snippets.
- LLM output citations still must map to system reference numbers.
- Bad LLM output falls back deterministic.

---

## Batch 8: RAG v2 For PDF And Multi-Document Search

**Goal:** Improve long-document retrieval without jumping directly to heavy pgvector production RAG.

### Task 8.1: PDF Outline/TOC Extraction

**Files:**

- Modify: `src/insight_graph/tools/document_reader.py`
- Modify: `src/insight_graph/report_quality/document_index.py`
- Test: `tests/test_document_reader.py` if exists, otherwise `tests/test_tools.py` or new focused test
- Test: `tests/test_validate_pdf_fetch.py`

**Behavior:**

- Extract PDF outline/bookmarks when available.
- Store outline labels in chunk metadata when page ranges match.

### Task 8.2: Page Range And Section Filters

**Files:**

- Modify: `src/insight_graph/tools/search_document.py`
- Test: `tests/test_tools.py` or `tests/test_search_document.py` if created

**Behavior:**

- JSON input supports `page_start`, `page_end`, and `section` filters.
- Existing `page` filter continues to work.

### Task 8.3: Multi-Document Search

**Files:**

- Modify: `src/insight_graph/tools/search_document.py`
- Modify: `src/insight_graph/tools/document_reader.py` only if needed
- Test: `tests/test_tools.py` or `tests/test_search_document.py`

**Behavior:**

- JSON input supports `paths: [...]`.
- Results are ranked across documents and preserve `source_url`.

### Task 8.4: Remote PDF Cache/Index

**Files:**

- Create: `src/insight_graph/tools/fetch_cache.py`
- Modify: `src/insight_graph/tools/fetch_url.py`
- Test: `tests/test_fetch_cache.py`
- Test: `tests/test_fetch_url.py`

**Behavior:**

- Optional `INSIGHT_GRAPH_FETCH_CACHE_DIR` caches fetched bytes by canonical URL hash.
- Cache respects max bytes and MIME checks.
- Default remains no cache.

---

## Batch 9: GitHub And SEC Deepening

**Goal:** Make professional data sources deeper and more useful.

### Task 9.1: GitHub README And Releases Evidence

**Files:**

- Modify: `src/insight_graph/tools/github_search.py`
- Test: `tests/test_validate_github_search.py`
- Test: `tests/test_tools.py`

**Behavior:**

- live GitHub search can fetch README and latest releases for returned repos when budget allows.
- Evidence IDs distinguish repo metadata, README, and release evidence.
- Tests fake API responses.

### Task 9.2: SEC Ticker Resolver Expansion

**Files:**

- Modify: `src/insight_graph/tools/sec_filings.py`
- Modify: `src/insight_graph/report_quality/entity_resolver.py`
- Test: `tests/test_tools.py`
- Test: `tests/test_entity_resolver.py`

**Behavior:**

- Add deterministic local ticker map file or broaden current resolver.
- Do not call live SEC in tests.

### Task 9.3: SEC Filing Content Fetch/Parse

**Files:**

- Modify: `src/insight_graph/tools/sec_filings.py`
- Test: `tests/test_tools.py`

**Behavior:**

- Optional `INSIGHT_GRAPH_SEC_FETCH_FILING_CONTENT=1` fetches filing text/HTML for 10-K/10-Q.
- Extracts bounded snippets for risk/business/MD&A-like headings.
- Uses existing `fetch_url` safety boundary.

---

## Batch 10: Production Persistence And Worker Resume

**Goal:** Make checkpoint/memory/job persistence deployable.

### Task 10.1: Migration Runner

**Files:**

- Create: `src/insight_graph/persistence/migrations.py`
- Modify: `src/insight_graph/persistence/checkpoints.py`
- Modify: `src/insight_graph/memory/store.py`
- Test: `tests/test_migrations.py`
- Test: `tests/test_checkpoints.py`
- Test: `tests/test_memory.py`

**Behavior:**

- Create `insight_graph_schema_migrations` table.
- Migrations are idempotent and ordered.
- Existing checkpoint/memory tables move from scattered `CREATE TABLE` to migration definitions.

### Task 10.2: Durable Job Worker Poller

**Files:**

- Modify: `src/insight_graph/api.py`
- Modify: `src/insight_graph/research_jobs_sqlite_backend.py`
- Test: `tests/test_api.py`
- Test: `tests/test_research_jobs_sqlite_backend.py`

**Behavior:**

- On startup, worker can claim queued/expired jobs from SQLite backend.
- Memory backend behavior unchanged.
- Tests use fake executor/backend.

### Task 10.3: Checkpoint Resume Routing Fixes

**Files:**

- Modify: `src/insight_graph/graph.py`
- Test: `tests/test_graph.py`

**Behavior:**

- If checkpoint is after Critic and `critique.passed=False`, resume routes to Planner/Collector rather than directly Reporter.
- If Critic passed, resume routes Reporter.

---

## Batch 11: Memory Lifecycle And API

**Goal:** Turn memory from opt-in read surface into useful long-term research memory.

### Task 11.1: Report Memory Writeback

**Files:**

- Create: `src/insight_graph/memory/writeback.py`
- Modify: `src/insight_graph/graph.py` or API job completion path
- Test: `tests/test_memory.py`

**Behavior:**

- On successful report, write summary, entities, supported claims, references metadata when `INSIGHT_GRAPH_MEMORY_WRITEBACK=1`.
- Default disabled.

### Task 11.2: Memory API Endpoints

**Files:**

- Modify: `src/insight_graph/api.py`
- Test: `tests/test_api.py`

**Behavior:**

- Add list/search/delete endpoints for memory records.
- Respect existing API key auth.

### Task 11.3: Memory On/Off Eval Proof

**Files:**

- Modify: `src/insight_graph/eval.py` or add script under `scripts/`
- Test: `tests/test_eval.py`

**Behavior:**

- Offline eval mode compares memory disabled vs fake memory context enabled.
- Outputs simple quality delta metadata.

---

## Batch 12: Observability And Dashboard v2

**Goal:** Make evidence, tools, citations, LLM calls, and quality visible in the product UI/API.

### Task 12.1: Trace ID Propagation

**Files:**

- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/api.py`
- Modify: `src/insight_graph/graph.py`
- Test: `tests/test_api.py`
- Test: `tests/test_graph.py`

**Behavior:**

- Add `trace_id` to `GraphState`.
- API jobs and synchronous runs expose trace ID.
- Tool/LLM logs include trace ID if adding field is low risk.

### Task 12.2: Dashboard Evidence/Citation Panels

**Files:**

- Modify: `src/insight_graph/dashboard.py`
- Modify: `src/insight_graph/api.py` if payload shaping needed
- Test: dashboard tests if present, otherwise API response tests

**Behavior:**

- Dashboard shows source candidates, fetch errors, citation support, URL validation, LLM token totals, quality cards.
- No build step.

### Task 12.3: Trace Redaction Controls

**Files:**

- Modify: `src/insight_graph/llm/trace_writer.py`
- Test: `tests/test_llm_client.py` or new trace tests

**Behavior:**

- Configurable redaction keeps secrets and optionally strips prompts/completions.
- Full trace remains explicit opt-in.

---

## Batch 13: Live Benchmark

**Goal:** Add a manual/opt-in benchmark for real networked research quality.

### Task 13.1: Live Benchmark Script

**Files:**

- Create: `scripts/benchmark_live_research.py`
- Test: `tests/test_benchmark_live_research.py`

**Behavior:**

- Requires `--allow-live` or `INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1`.
- Runs configured cases through `--preset live-research`.
- Writes JSON artifact with URL validity, citation precision proxy, source diversity, report depth, runtime, LLM call counts, token counts.
- Tests fake `run_research`; no live network.

### Task 13.2: Live Benchmark Docs

**Files:**

- Modify: `README.md`
- Modify: `docs/scripts.md`
- Modify: `docs/configuration.md`

**Behavior:**

- Explain live benchmark is manual/opt-in and may incur network/LLM cost.

---

## Batch 14: Docs Final Alignment

**Goal:** Remove stale docs and make the product story consistent.

**Files:**

- `README.md`
- `docs/configuration.md`
- `docs/architecture.md`
- `docs/scripts.md`
- `docs/reference-parity-roadmap.md`
- `docs/report-quality-roadmap.md`
- `docs/roadmap.md`

**Behavior:**

- Docs state product path is `live-research`.
- Offline remains testing/CI fallback.
- Update status of completed batches.
- Keep safety/opt-in boundaries clear.

**Verification:**

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_repository_hygiene.py tests/test_ci_workflow.py -q
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

---

## Deferred Until Explicit Approval

These are intentionally last because they expand attack surface or scope:

1. MCP runtime invocation behind allowlist.
2. Real sandboxed Python/code execution.
3. `/tasks` API compatibility aliases unless a real consumer requires them.
4. Force-push/release/deploy automation.

## Recommended Immediate Next Batch

Start with **Batch 1: Finish Fetch Reliability And Source Semantics**.

Execution order inside Batch 1:

1. Canonical URL normalization and dedupe.
2. Source type v2.
3. Verification-state metadata.
4. Retry/backoff and error taxonomy.
5. Docs and desktop status update.
6. Full verification and merge.
