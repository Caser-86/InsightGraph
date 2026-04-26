# Competitive Matrix MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a structured, evidence-backed competitive matrix to default analysis, Markdown reports, and JSON output.

**Architecture:** Store matrix rows in `GraphState` as Pydantic models, generate them deterministically in Analyst from verified evidence, and render them in Reporter using the existing reference-number system. LLM Analyst may provide matrix rows, but Reporter remains deterministic for matrix rendering so citations stay validated.

**Tech Stack:** Python 3.13, Pydantic, pytest, ruff, existing InsightGraph agents and CLI.

---

## File Structure

- Modify `src/insight_graph/state.py`: add `CompetitiveMatrixRow` and `GraphState.competitive_matrix`.
- Modify `src/insight_graph/agents/analyst.py`: add deterministic matrix builder and optional LLM matrix parsing.
- Modify `src/insight_graph/agents/reporter.py`: render `## Competitive Matrix` in deterministic and LLM reports.
- Modify `src/insight_graph/cli.py`: include `competitive_matrix` in `--output-json` payload.
- Modify `README.md`: document current Competitive Matrix MVP capability and limits.
- Modify `tests/test_state.py`: cover default matrix state.
- Modify `tests/test_agents.py`: cover Analyst and Reporter behavior.
- Modify `tests/test_cli.py`: cover JSON payload.
- Modify `tests/test_graph.py`: cover full graph report includes matrix.

---

### Task 1: Add Competitive Matrix State And Deterministic Analyst

**Files:**
- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/agents/analyst.py`
- Modify: `tests/test_state.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Write failing state and deterministic Analyst tests**

In `tests/test_state.py`, update the state import:

```python
from insight_graph.state import (
    CompetitiveMatrixRow,
    Evidence,
    GraphState,
    LLMCallRecord,
    Subtask,
    ToolCallRecord,
)
```

Update `test_graph_state_starts_with_empty_collections()`:

```python
def test_graph_state_starts_with_empty_collections() -> None:
    state = GraphState(user_request="Analyze AI coding agents")

    assert state.user_request == "Analyze AI coding agents"
    assert state.subtasks == []
    assert state.evidence_pool == []
    assert state.findings == []
    assert state.competitive_matrix == []
    assert state.report_markdown is None
```

Add this test after `test_graph_state_starts_with_empty_collections()`:

```python
def test_competitive_matrix_row_stores_evidence_backed_fields() -> None:
    row = CompetitiveMatrixRow(
        product="Cursor",
        positioning="Official product positioning signal",
        strengths=["Official/documented source coverage"],
        evidence_ids=["cursor-pricing"],
    )

    assert row.product == "Cursor"
    assert row.positioning == "Official product positioning signal"
    assert row.strengths == ["Official/documented source coverage"]
    assert row.evidence_ids == ["cursor-pricing"]
```

In `tests/test_agents.py`, update the state import:

```python
from insight_graph.state import (
    CompetitiveMatrixRow,
    Critique,
    Evidence,
    Finding,
    GraphState,
)
```

Add this helper after `make_analyst_state()`:

```python
def make_matrix_state() -> GraphState:
    return GraphState(
        user_request="Compare Cursor, OpenCode, and GitHub Copilot",
        evidence_pool=[
            Evidence(
                id="cursor-pricing",
                subtask_id="collect",
                title="Cursor Pricing",
                source_url="https://cursor.com/pricing",
                snippet="Cursor lists pricing and AI coding features.",
                source_type="official_site",
                verified=True,
            ),
            Evidence(
                id="opencode-repo",
                subtask_id="collect",
                title="OpenCode Repository",
                source_url="https://github.com/sst/opencode",
                snippet="OpenCode repository shows developer ecosystem activity.",
                source_type="github",
                verified=True,
            ),
            Evidence(
                id="copilot-docs",
                subtask_id="collect",
                title="GitHub Copilot Documentation",
                source_url="https://docs.github.com/en/copilot",
                snippet="GitHub Copilot documentation describes coding assistant features.",
                source_type="docs",
                verified=True,
            ),
            Evidence(
                id="unverified-cursor-blog",
                subtask_id="collect",
                title="Cursor Blog",
                source_url="https://example.com/cursor",
                snippet="Unverified Cursor opinion.",
                source_type="blog",
                verified=False,
            ),
        ],
    )
```

Add these tests after the deterministic Analyst tests:

```python
def test_deterministic_analyst_builds_competitive_matrix() -> None:
    state = make_matrix_state()

    updated = analyze_evidence(state)

    products = [row.product for row in updated.competitive_matrix]
    assert products == ["Cursor", "OpenCode", "GitHub Copilot"]
    cursor = updated.competitive_matrix[0]
    opencode = updated.competitive_matrix[1]
    copilot = updated.competitive_matrix[2]
    assert cursor.positioning == "Official product positioning signal"
    assert opencode.positioning == "Open-source or developer ecosystem signal"
    assert copilot.positioning == "Documented product or local research source"
    assert cursor.evidence_ids == ["cursor-pricing"]
    assert opencode.evidence_ids == ["opencode-repo"]
    assert copilot.evidence_ids == ["copilot-docs"]
    assert "unverified-cursor-blog" not in cursor.evidence_ids
```

```python
def test_deterministic_analyst_matrix_uses_general_row_without_product_match() -> None:
    state = GraphState(
        user_request="Analyze developer tool market",
        evidence_pool=[
            Evidence(
                id="market-news",
                subtask_id="collect",
                title="AI developer tools funding",
                source_url="https://example.com/news",
                snippet="Developer tool market activity increased.",
                source_type="news",
                verified=True,
            )
        ],
    )

    updated = analyze_evidence(state)

    assert len(updated.competitive_matrix) == 1
    assert updated.competitive_matrix[0].product == "General market evidence"
    assert updated.competitive_matrix[0].evidence_ids == ["market-news"]
```

```python
def test_deterministic_analyst_matrix_empty_without_verified_evidence() -> None:
    state = GraphState(
        user_request="Compare Cursor and GitHub Copilot",
        evidence_pool=[
            Evidence(
                id="unverified",
                subtask_id="collect",
                title="Cursor Blog",
                source_url="https://example.com/cursor",
                snippet="Unverified Cursor opinion.",
                source_type="blog",
                verified=False,
            )
        ],
    )

    updated = analyze_evidence(state)

    assert updated.competitive_matrix == []
```

- [ ] **Step 2: Run state/Analyst tests and verify RED**

Run:

```powershell
python -m pytest tests/test_state.py::test_graph_state_starts_with_empty_collections tests/test_state.py::test_competitive_matrix_row_stores_evidence_backed_fields tests/test_agents.py::test_deterministic_analyst_builds_competitive_matrix tests/test_agents.py::test_deterministic_analyst_matrix_uses_general_row_without_product_match tests/test_agents.py::test_deterministic_analyst_matrix_empty_without_verified_evidence -q
```

Expected: FAIL because `CompetitiveMatrixRow` and `GraphState.competitive_matrix` do not exist.

- [ ] **Step 3: Add state schema**

In `src/insight_graph/state.py`, add after `Finding`:

```python
class CompetitiveMatrixRow(BaseModel):
    product: str
    positioning: str
    strengths: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
```

Add to `GraphState` after `findings`:

```python
    competitive_matrix: list[CompetitiveMatrixRow] = Field(default_factory=list)
```

- [ ] **Step 4: Implement deterministic matrix builder**

In `src/insight_graph/agents/analyst.py`, update import:

```python
from insight_graph.state import CompetitiveMatrixRow, Evidence, Finding, GraphState
```

Add constants near the top:

```python
PRODUCT_ALIASES = {
    "Cursor": ["cursor"],
    "OpenCode": ["opencode", "open code"],
    "Claude Code": ["claude code"],
    "GitHub Copilot": ["github copilot", "copilot"],
    "Codeium": ["codeium"],
    "Windsurf": ["windsurf"],
}

SOURCE_POSITIONING = {
    "github": "Open-source or developer ecosystem signal",
    "docs": "Documented product or local research source",
    "news": "Market/news activity signal",
    "official_site": "Official product positioning signal",
}

SOURCE_STRENGTHS = {
    "official_site": "Official/documented source coverage",
    "docs": "Official/documented source coverage",
    "github": "Repository or developer ecosystem evidence",
    "news": "News or launch activity evidence",
}
```

Update `_analyze_evidence_deterministic()`:

```python
def _analyze_evidence_deterministic(state: GraphState) -> GraphState:
    evidence_ids = [item.id for item in state.evidence_pool]
    state.findings = [
        Finding(
            title="Official sources establish baseline product positioning",
            summary=(
                "Official pricing pages, documentation, and repositories provide the safest "
                "baseline for comparing product positioning and capabilities."
            ),
            evidence_ids=evidence_ids[:2],
        ),
        Finding(
            title="Open repositories add adoption and roadmap signals",
            summary=(
                "GitHub evidence helps evaluate public development activity, release cadence, "
                "and community-facing positioning."
            ),
            evidence_ids=evidence_ids[2:],
        ),
    ]
    state.competitive_matrix = build_competitive_matrix(
        state.user_request,
        state.evidence_pool,
    )
    return state
```

Add helpers after `_analyze_evidence_deterministic()`:

```python
def build_competitive_matrix(
    user_request: str,
    evidence_pool: list[Evidence],
) -> list[CompetitiveMatrixRow]:
    verified_evidence = [item for item in evidence_pool if item.verified]
    if not verified_evidence:
        return []

    rows = []
    for product, aliases in PRODUCT_ALIASES.items():
        product_evidence = [
            item
            for item in verified_evidence
            if _mentions_product(user_request, item, aliases)
        ]
        if not product_evidence:
            continue
        rows.append(_build_matrix_row(product, product_evidence[:3]))

    if rows:
        return rows
    return [_build_matrix_row("General market evidence", verified_evidence[:3])]


def _mentions_product(user_request: str, evidence: Evidence, aliases: list[str]) -> bool:
    haystack = " ".join([user_request, evidence.title, evidence.snippet]).lower()
    return any(alias in haystack for alias in aliases)


def _build_matrix_row(product: str, evidence: list[Evidence]) -> CompetitiveMatrixRow:
    source_types = [item.source_type for item in evidence]
    positioning = _positioning_for_sources(source_types)
    strengths = _strengths_for_sources(source_types)
    return CompetitiveMatrixRow(
        product=product,
        positioning=positioning,
        strengths=strengths,
        evidence_ids=[item.id for item in evidence],
    )


def _positioning_for_sources(source_types: list[str]) -> str:
    for source_type in ("github", "docs", "news", "official_site"):
        if source_type in source_types:
            return SOURCE_POSITIONING[source_type]
    return "Evidence-backed product signal"


def _strengths_for_sources(source_types: list[str]) -> list[str]:
    strengths = []
    for source_type in ("official_site", "docs", "github", "news"):
        strength = SOURCE_STRENGTHS.get(source_type)
        if source_type in source_types and strength and strength not in strengths:
            strengths.append(strength)
    if not strengths:
        strengths.append("Verified evidence available")
    return strengths[:3]
```

- [ ] **Step 5: Run state/Analyst tests and lint**

Run:

```powershell
python -m pytest tests/test_state.py tests/test_agents.py::test_deterministic_analyst_builds_competitive_matrix tests/test_agents.py::test_deterministic_analyst_matrix_uses_general_row_without_product_match tests/test_agents.py::test_deterministic_analyst_matrix_empty_without_verified_evidence -q
python -m ruff check src/insight_graph/state.py src/insight_graph/agents/analyst.py tests/test_state.py tests/test_agents.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add src/insight_graph/state.py src/insight_graph/agents/analyst.py tests/test_state.py tests/test_agents.py
git commit -m "feat: add competitive matrix state"
```

---

### Task 2: Add LLM Analyst Matrix Parsing

**Files:**
- Modify: `src/insight_graph/agents/analyst.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Write failing LLM Analyst tests**

Add these tests near the existing LLM Analyst parser tests:

```python
def test_llm_analyst_parses_competitive_matrix(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()
    client = UsageLLMClient(
        content=(
            '{"findings":[{"title":"Packaging differs",'
            '"summary":"Cursor and Copilot use different packaging signals.",'
            '"evidence_ids":["cursor-pricing"]}],'
            '"competitive_matrix":[{"product":"Cursor",'
            '"positioning":"Official product positioning signal",'
            '"strengths":["Official/documented source coverage"],'
            '"evidence_ids":["cursor-pricing"]}]}'
        )
    )

    updated = analyze_evidence(state, llm_client=client)

    assert updated.competitive_matrix == [
        CompetitiveMatrixRow(
            product="Cursor",
            positioning="Official product positioning signal",
            strengths=["Official/documented source coverage"],
            evidence_ids=["cursor-pricing"],
        )
    ]
```

```python
def test_llm_analyst_uses_deterministic_matrix_when_matrix_missing(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()
    client = UsageLLMClient(
        content=(
            '{"findings":[{"title":"Packaging differs",'
            '"summary":"Cursor and Copilot use different packaging signals.",'
            '"evidence_ids":["cursor-pricing"]}]}'
        )
    )

    updated = analyze_evidence(state, llm_client=client)

    assert [row.product for row in updated.competitive_matrix] == [
        "Cursor",
        "GitHub Copilot",
    ]
```

```python
def test_llm_analyst_falls_back_for_invalid_competitive_matrix(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()
    client = UsageLLMClient(
        content=(
            '{"findings":[{"title":"Packaging differs",'
            '"summary":"Cursor and Copilot use different packaging signals.",'
            '"evidence_ids":["cursor-pricing"]}],'
            '"competitive_matrix":[{"product":"Cursor",'
            '"positioning":"Official product positioning signal",'
            '"strengths":["Official/documented source coverage"],'
            '"evidence_ids":["missing-evidence"]}]}'
        )
    )

    updated = analyze_evidence(state, llm_client=client)

    assert [row.product for row in updated.competitive_matrix] == [
        "Cursor",
        "GitHub Copilot",
    ]
```

- [ ] **Step 2: Run LLM Analyst tests and verify RED**

Run:

```powershell
python -m pytest tests/test_agents.py::test_llm_analyst_parses_competitive_matrix tests/test_agents.py::test_llm_analyst_uses_deterministic_matrix_when_matrix_missing tests/test_agents.py::test_llm_analyst_falls_back_for_invalid_competitive_matrix -q
```

Expected: FAIL because LLM Analyst does not parse/populate `competitive_matrix` yet.

- [ ] **Step 3: Implement LLM matrix parsing**

In `_analyze_evidence_with_llm()`, replace the parse assignment:

```python
        state.findings = _parse_analyst_findings(result.content, state.evidence_pool)
        state.competitive_matrix = build_competitive_matrix(
            state.user_request,
            state.evidence_pool,
        )
```

with:

```python
        state.findings, parsed_matrix = _parse_analyst_response(
            result.content,
            state.evidence_pool,
        )
        state.competitive_matrix = parsed_matrix or build_competitive_matrix(
            state.user_request,
            state.evidence_pool,
        )
```

Add parser helpers after `_parse_analyst_findings()`:

```python
def _parse_analyst_response(
    content: str | None,
    evidence_pool: list[Evidence],
) -> tuple[list[Finding], list[CompetitiveMatrixRow]]:
    data = _load_analyst_json(content)
    findings = _parse_analyst_findings_from_data(data, evidence_pool)
    matrix = _parse_competitive_matrix_from_data(data, evidence_pool)
    return findings, matrix


def _load_analyst_json(content: str | None) -> dict:
    if not content:
        raise ValueError("LLM response content is required")
    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("LLM response must be valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")
    return data


def _parse_analyst_findings(content: str | None, evidence_pool: list[Evidence]) -> list[Finding]:
    data = _load_analyst_json(content)
    return _parse_analyst_findings_from_data(data, evidence_pool)
```

Move the existing body of `_parse_analyst_findings()` into `_parse_analyst_findings_from_data(data, evidence_pool)` and keep the same validations.

Add:

```python
def _parse_competitive_matrix_from_data(
    data: dict,
    evidence_pool: list[Evidence],
) -> list[CompetitiveMatrixRow]:
    raw_matrix = data.get("competitive_matrix")
    if raw_matrix is None:
        return []
    if not isinstance(raw_matrix, list):
        raise ValueError("LLM competitive_matrix must be a list")

    verified_evidence_ids = {item.id for item in evidence_pool if item.verified}
    matrix = []
    for raw_row in raw_matrix:
        if not isinstance(raw_row, dict):
            raise ValueError("LLM competitive_matrix row must be an object")
        product = raw_row.get("product")
        positioning = raw_row.get("positioning")
        strengths = raw_row.get("strengths", [])
        evidence_ids = raw_row.get("evidence_ids")
        if not isinstance(product, str) or not product.strip():
            raise ValueError("LLM competitive_matrix product is required")
        if not isinstance(positioning, str) or not positioning.strip():
            raise ValueError("LLM competitive_matrix positioning is required")
        if not isinstance(strengths, list) or not all(
            isinstance(item, str) and item.strip() for item in strengths
        ):
            raise ValueError("LLM competitive_matrix strengths must be strings")
        if len(strengths) > 5:
            raise ValueError("LLM competitive_matrix strengths must have at most 5 items")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise ValueError("LLM competitive_matrix evidence_ids are required")
        if not all(
            isinstance(evidence_id, str) and evidence_id.strip()
            for evidence_id in evidence_ids
        ):
            raise ValueError("LLM competitive_matrix evidence_ids must be strings")
        if not set(evidence_ids).issubset(verified_evidence_ids):
            raise ValueError("LLM competitive_matrix cites unverified or unknown evidence")
        matrix.append(
            CompetitiveMatrixRow(
                product=product.strip(),
                positioning=positioning.strip(),
                strengths=[item.strip() for item in strengths],
                evidence_ids=evidence_ids,
            )
        )
    return matrix
```

- [ ] **Step 4: Run LLM Analyst tests and lint**

Run:

```powershell
python -m pytest tests/test_agents.py::test_llm_analyst_parses_competitive_matrix tests/test_agents.py::test_llm_analyst_uses_deterministic_matrix_when_matrix_missing tests/test_agents.py::test_llm_analyst_falls_back_for_invalid_competitive_matrix -q
python -m ruff check src/insight_graph/agents/analyst.py tests/test_agents.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add src/insight_graph/agents/analyst.py tests/test_agents.py
git commit -m "feat: parse competitive matrix from analyst"
```

---

### Task 3: Render Matrix In Reporter And JSON Output

**Files:**
- Modify: `src/insight_graph/agents/reporter.py`
- Modify: `src/insight_graph/cli.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Write failing Reporter and CLI tests**

Update `make_reporter_state()` in `tests/test_agents.py` to include:

```python
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Cursor",
                positioning="Official product positioning signal",
                strengths=["Official/documented source coverage"],
                evidence_ids=["cursor-pricing"],
            ),
            CompetitiveMatrixRow(
                product="GitHub Copilot",
                positioning="Documented product or local research source",
                strengths=["Official/documented source coverage"],
                evidence_ids=["copilot-docs"],
            ),
        ],
```

Add these reporter tests:

```python
def test_reporter_renders_competitive_matrix() -> None:
    state = make_reporter_state()

    updated = write_report(state)

    assert "## Competitive Matrix" in updated.report_markdown
    assert "| Product | Positioning | Strengths | Evidence |" in updated.report_markdown
    assert "| Cursor | Official product positioning signal | Official/documented source coverage | [1] |" in updated.report_markdown
    assert "| GitHub Copilot | Documented product or local research source | Official/documented source coverage | [2] |" in updated.report_markdown
    assert updated.report_markdown.index("## Key Findings") < updated.report_markdown.index("## Competitive Matrix")
    assert updated.report_markdown.index("## Competitive Matrix") < updated.report_markdown.index("## Critic Assessment")
```

```python
def test_reporter_omits_competitive_matrix_without_citable_rows() -> None:
    state = make_reporter_state()
    state.competitive_matrix = [
        CompetitiveMatrixRow(
            product="Cursor",
            positioning="Official product positioning signal",
            strengths=["Official/documented source coverage"],
            evidence_ids=["missing-evidence"],
        )
    ]

    updated = write_report(state)

    assert "## Competitive Matrix" not in updated.report_markdown
```

```python
def test_llm_reporter_inserts_competitive_matrix_when_missing(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    state = make_reporter_state()
    client = UsageLLMClient(
        content=(
            '{"markdown":"# InsightGraph Research Report\\n\\n## Key Findings\\n\\n'
            'Cursor differs from Copilot [1]."}'
        )
    )

    updated = write_report(state, llm_client=client)

    assert "## Competitive Matrix" in updated.report_markdown
    assert "| Cursor | Official product positioning signal | Official/documented source coverage | [1] |" in updated.report_markdown
```

```python
def test_llm_reporter_does_not_duplicate_competitive_matrix(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    state = make_reporter_state()
    client = UsageLLMClient(
        content=(
            '{"markdown":"# InsightGraph Research Report\\n\\n## Key Findings\\n\\n'
            'Cursor differs from Copilot [1].\\n\\n## Competitive Matrix\\n\\n'
            '| Product | Positioning | Strengths | Evidence |\\n'
            '| --- | --- | --- | --- |\\n'
            '| Cursor | Existing | Existing | [1] |"}'
        )
    )

    updated = write_report(state, llm_client=client)

    assert updated.report_markdown.count("## Competitive Matrix") == 1
    assert "| Cursor | Existing | Existing | [1] |" in updated.report_markdown
```

In `tests/test_cli.py`, update imports to include `CompetitiveMatrixRow` and add:

```python
def test_cli_json_payload_includes_competitive_matrix(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return GraphState(
            user_request=query,
            competitive_matrix=[
                CompetitiveMatrixRow(
                    product="Cursor",
                    positioning="Official product positioning signal",
                    strengths=["Official/documented source coverage"],
                    evidence_ids=["cursor-pricing"],
                )
            ],
            report_markdown="# Report\n",
        )

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents", "--output-json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["competitive_matrix"] == [
        {
            "product": "Cursor",
            "positioning": "Official product positioning signal",
            "strengths": ["Official/documented source coverage"],
            "evidence_ids": ["cursor-pricing"],
        }
    ]
```

In `tests/test_graph.py`, update `test_run_research_executes_full_graph()`:

```python
    assert "## Competitive Matrix" in result.report_markdown
    assert result.competitive_matrix
```

- [ ] **Step 2: Run Reporter/CLI tests and verify RED**

Run:

```powershell
python -m pytest tests/test_agents.py::test_reporter_renders_competitive_matrix tests/test_agents.py::test_reporter_omits_competitive_matrix_without_citable_rows tests/test_agents.py::test_llm_reporter_inserts_competitive_matrix_when_missing tests/test_agents.py::test_llm_reporter_does_not_duplicate_competitive_matrix tests/test_cli.py::test_cli_json_payload_includes_competitive_matrix tests/test_graph.py::test_run_research_executes_full_graph -q
```

Expected: FAIL because Reporter/CLI do not render or serialize matrix yet.

- [ ] **Step 3: Implement Reporter matrix rendering**

In `src/insight_graph/agents/reporter.py`, update import:

```python
from insight_graph.state import CompetitiveMatrixRow, Evidence, GraphState
```

In `_write_report_deterministic()`, after the findings loop and before critic section:

```python
    lines.extend(_build_competitive_matrix_section(state.competitive_matrix, reference_numbers))
```

In `_write_report_with_llm()`, after `lines = [body.rstrip(), ""]` and before critic section:

```python
    if "## Competitive Matrix" not in body:
        lines.extend(_build_competitive_matrix_section(state.competitive_matrix, reference_numbers))
```

Add helpers before `_build_critic_assessment_section()`:

```python
def _build_competitive_matrix_section(
    matrix: list[CompetitiveMatrixRow],
    reference_numbers: dict[str, int],
) -> list[str]:
    rows = []
    for row in matrix:
        citations = [
            f"[{reference_numbers[evidence_id]}]"
            for evidence_id in row.evidence_ids
            if evidence_id in reference_numbers
        ]
        if not citations:
            continue
        strengths = "; ".join(row.strengths) if row.strengths else "Verified evidence available"
        rows.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(row.product),
                    _markdown_table_cell(row.positioning),
                    _markdown_table_cell(strengths),
                    ", ".join(citations),
                ]
            )
            + " |"
        )
    if not rows:
        return []
    return [
        "## Competitive Matrix",
        "",
        "| Product | Positioning | Strengths | Evidence |",
        "| --- | --- | --- | --- |",
        *rows,
        "",
    ]
```

- [ ] **Step 4: Add CLI JSON field**

In `src/insight_graph/cli.py`, add to `_build_research_json_payload()` after findings:

```python
        "competitive_matrix": [
            row.model_dump(mode="json") for row in state.competitive_matrix
        ],
```

- [ ] **Step 5: Run Reporter/CLI tests and lint**

Run:

```powershell
python -m pytest tests/test_agents.py tests/test_cli.py tests/test_graph.py -q
python -m ruff check src/insight_graph/agents/reporter.py src/insight_graph/cli.py tests/test_agents.py tests/test_cli.py tests/test_graph.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add src/insight_graph/agents/reporter.py src/insight_graph/cli.py tests/test_agents.py tests/test_cli.py tests/test_graph.py
git commit -m "feat: render competitive matrix"
```

---

### Task 4: Document Competitive Matrix MVP

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README feature descriptions**

In the Analyst section around `### 3. Analyst`, update the competitive matrix bullet to:

```markdown
- **竞品矩阵**：当前 MVP 生成 evidence-backed deterministic `competitive_matrix`，Reporter 输出 `Competitive Matrix` Markdown 表格；第一版不做排名、评分或精确定价抽取
```

In the current output section, add:

```markdown
- **结构化输出**：`--output-json` 包含 `competitive_matrix`，便于后续 API、benchmark 和前端复用
```

In the example output structure, keep `Competitive Matrix` and add one sentence:

```markdown
当前 `Competitive Matrix` 为 verified evidence 支撑的 deterministic MVP；它展示产品、定位、证据标签和引用，不代表自动排名或评分。
```

- [ ] **Step 2: Run docs-related verification**

Run:

```powershell
python -m pytest tests/test_agents.py::test_reporter_renders_competitive_matrix tests/test_cli.py::test_cli_json_payload_includes_competitive_matrix -q
python -m ruff check .
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 3: Commit Task 4**

Run:

```powershell
git add README.md
git commit -m "docs: document competitive matrix mvp"
```

---

### Task 5: Final Verification And CLI Smoke

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_state.py tests/test_agents.py tests/test_cli.py tests/test_graph.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full tests and lint**

Run:

```powershell
python -m pytest -q
python -m ruff check .
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 3: Reinstall editable checkout for CLI smoke**

Run:

```powershell
python -m pip install -e .
```

Expected: command succeeds and installs the current checkout.

- [ ] **Step 4: Run JSON CLI smoke**

Run and parse matrix length:

```powershell
Remove-Item Env:\INSIGHT_GRAPH_USE_WRITE_FILE -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_READ_FILE -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_LIST_DIRECTORY -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_DOCUMENT_READER -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_NEWS_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_GITHUB_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json | python -c "import sys,json; data=json.load(sys.stdin); print(len(data['competitive_matrix'])); print(data['competitive_matrix'][0]['product'])"
```

Expected output first line is greater than `0`; second line is a product name such as `Cursor`.

- [ ] **Step 5: Run Markdown CLI smoke**

Run and assert matrix heading appears:

```powershell
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" | python -c "import sys; text=sys.stdin.read(); print('## Competitive Matrix' in text)"
```

Expected output: `True`.

- [ ] **Step 6: Inspect git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree on the implementation branch.
