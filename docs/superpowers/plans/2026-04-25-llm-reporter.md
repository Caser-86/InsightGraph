# LLM Reporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in OpenAI-compatible LLM Reporter that improves report prose while preserving deterministic defaults and system-controlled citations.

**Architecture:** Keep the feature local to `reporter.py`: split deterministic rendering into helpers, add an LLM provider branch, validate the LLM body, strip LLM references, and append deterministic references. Tests use fake LLM clients only and default paths remain offline.

**Tech Stack:** Python 3.11+, Pydantic models, OpenAI-compatible shared LLM client, Pytest, Ruff.

---

## File Structure

- Modify: `src/insight_graph/agents/reporter.py` - add provider resolution, deterministic helper split, LLM Reporter path, citation validation, and deterministic reference assembly.
- Modify: `tests/test_agents.py` - add Reporter provider tests, fake LLM Reporter tests, fallback tests, and env isolation.
- Modify: `tests/test_cli.py` - clear LLM/Reporter env for default CLI smoke test.
- Modify: `tests/test_graph.py` - clear LLM/Reporter env for default graph tests.
- Modify: `README.md` - document LLM Reporter env vars and update MVP note about LLM routing.

---

### Task 1: Reporter Provider And Deterministic Refactor

**Files:**
- Modify: `src/insight_graph/agents/reporter.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Add failing provider tests**

Modify the import in `tests/test_agents.py` from:

```python
from insight_graph.agents.reporter import write_report
```

to:

```python
from insight_graph.agents.reporter import get_reporter_provider, write_report
```

Update `clear_llm_env` in `tests/test_agents.py` to also clear `INSIGHT_GRAPH_REPORTER_PROVIDER`:

```python
def clear_llm_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_PROVIDER",
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_LLM_BASE_URL",
        "INSIGHT_GRAPH_LLM_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.delenv(name, raising=False)
```

Modify `test_reporter_excludes_unverified_sources` in `tests/test_agents.py` from:

```python
def test_reporter_excludes_unverified_sources() -> None:
```

to:

```python
def test_reporter_excludes_unverified_sources(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
```

and keep the existing test body after the new `clear_llm_env(monkeypatch)` line.

Replace `tests/test_cli.py` with:

```python
from typer.testing import CliRunner

from insight_graph.cli import app


def clear_llm_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_PROVIDER",
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_LLM_BASE_URL",
        "INSIGHT_GRAPH_LLM_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_cli_research_outputs_markdown_report(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents"])

    assert result.exit_code == 0
    assert "# InsightGraph Research Report" in result.output
    assert "## References" in result.output
```

Replace `tests/test_graph.py` with:

```python
from insight_graph.graph import run_research
from insight_graph.state import GraphState


def clear_llm_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_PROVIDER",
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_LLM_BASE_URL",
        "INSIGHT_GRAPH_LLM_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_run_research_executes_full_graph(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    result = run_research("Compare Cursor, OpenCode, and GitHub Copilot")

    assert result.critique is not None
    assert result.critique.passed is True
    assert result.report_markdown is not None
    assert "# InsightGraph Research Report" in result.report_markdown
    assert "https://cursor.com/pricing" in result.report_markdown


def test_run_research_stops_after_failed_retry(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    import insight_graph.graph as graph_module

    def collect_no_evidence(state: GraphState) -> GraphState:
        state.evidence_pool = []
        return state

    monkeypatch.setattr(graph_module, "collect_evidence", collect_no_evidence)

    result = graph_module.run_research("Unknown product")

    assert result.critique is not None
    assert result.critique.passed is False
    assert result.iterations == 1
    assert result.report_markdown is not None
    assert "# InsightGraph Research Report" in result.report_markdown
    assert "Official sources establish baseline product positioning" not in result.report_markdown
    assert "Evidence, findings, or citation support are insufficient." in result.report_markdown
```

Append these tests to `tests/test_agents.py`:

```python

def test_get_reporter_provider_defaults_to_deterministic(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    assert get_reporter_provider() == "deterministic"


def test_get_reporter_provider_rejects_unknown_name(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "unknown")

    with pytest.raises(ValueError, match="Unknown reporter provider: unknown"):
        get_reporter_provider()


def test_reporter_defaults_to_deterministic_when_env_is_clear(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    state = GraphState(
        user_request="Compare AI coding agents",
        evidence_pool=[
            Evidence(
                id="verified-source",
                subtask_id="collect",
                title="Verified Source",
                source_url="https://example.com/verified",
                snippet="Verified evidence snippet.",
                verified=True,
            )
        ],
        findings=[
            Finding(
                title="Verified finding",
                summary="This finding cites verified evidence.",
                evidence_ids=["verified-source"],
            )
        ],
    )

    updated = write_report(state)

    assert updated.report_markdown is not None
    assert "### Verified finding" in updated.report_markdown
    assert "[1] Verified Source. https://example.com/verified" in updated.report_markdown
```

- [ ] **Step 2: Run provider tests to verify they fail**

Run: `python -m pytest tests/test_agents.py::test_get_reporter_provider_defaults_to_deterministic tests/test_agents.py::test_get_reporter_provider_rejects_unknown_name tests/test_agents.py::test_reporter_defaults_to_deterministic_when_env_is_clear -v`

Expected: FAIL with `ImportError` for `get_reporter_provider`.

- [ ] **Step 3: Refactor deterministic reporter and add provider resolution**

Replace `src/insight_graph/agents/reporter.py` with:

```python
import os

from insight_graph.state import Evidence, GraphState


def get_reporter_provider(name: str | None = None) -> str:
    provider = name or os.getenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "deterministic")
    if provider not in {"deterministic", "llm"}:
        raise ValueError(f"Unknown reporter provider: {provider}")
    return provider


def write_report(state: GraphState) -> GraphState:
    provider = get_reporter_provider()
    if provider == "deterministic":
        return _write_report_deterministic(state)
    return _write_report_deterministic(state)


def _write_report_deterministic(state: GraphState) -> GraphState:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    reference_numbers = _build_reference_numbers(verified_evidence)
    lines = [
        "# InsightGraph Research Report",
        "",
        f"**Research Request:** {state.user_request}",
        "",
        "## Key Findings",
        "",
    ]
    for finding in state.findings:
        citations = " ".join(
            f"[{reference_numbers[eid]}]"
            for eid in finding.evidence_ids
            if eid in reference_numbers
        )
        if not citations:
            continue
        lines.extend([f"### {finding.title}", "", f"{finding.summary} {citations}".strip(), ""])

    if state.critique is not None:
        lines.extend(_build_critic_assessment_section(state))

    lines.extend(_build_references_section(verified_evidence, reference_numbers))
    state.report_markdown = "\n".join(lines) + "\n"
    return state


def _build_reference_numbers(verified_evidence: list[Evidence]) -> dict[str, int]:
    return {item.id: index for index, item in enumerate(verified_evidence, start=1)}


def _build_critic_assessment_section(state: GraphState) -> list[str]:
    if state.critique is None:
        return []
    return ["## Critic Assessment", "", state.critique.reason, ""]


def _build_references_section(
    verified_evidence: list[Evidence],
    reference_numbers: dict[str, int],
) -> list[str]:
    lines = ["## References", ""]
    for item in verified_evidence:
        number = reference_numbers[item.id]
        lines.append(f"[{number}] {item.title}. {item.source_url}")
    return lines
```

The `llm` branch temporarily falls back to deterministic in this task. Task 2 will replace it with real LLM behavior.

- [ ] **Step 4: Run provider tests and existing reporter tests**

Run: `python -m pytest tests/test_agents.py::test_get_reporter_provider_defaults_to_deterministic tests/test_agents.py::test_get_reporter_provider_rejects_unknown_name tests/test_agents.py::test_reporter_defaults_to_deterministic_when_env_is_clear tests/test_agents.py::test_reporter_excludes_unverified_sources tests/test_agents.py::test_analysis_critic_and_reporter_create_cited_report tests/test_cli.py tests/test_graph.py -v`

Expected: selected tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 5: Commit**

```bash
git add src/insight_graph/agents/reporter.py tests/test_agents.py tests/test_cli.py tests/test_graph.py
git commit -m "feat: add reporter provider selection"
```

---

### Task 2: LLM Reporter Body And Citation Guardrails

**Files:**
- Modify: `src/insight_graph/agents/reporter.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Add failing LLM Reporter tests**

Append these helpers and tests to `tests/test_agents.py`:

```python

def make_reporter_state() -> GraphState:
    return GraphState(
        user_request="Compare Cursor and GitHub Copilot",
        evidence_pool=[
            Evidence(
                id="cursor-pricing",
                subtask_id="collect",
                title="Cursor Pricing",
                source_url="https://cursor.com/pricing",
                snippet="Cursor lists Pro and Business pricing tiers.",
                source_type="official_site",
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
                id="unverified-blog",
                subtask_id="collect",
                title="Unverified Blog",
                source_url="https://example.com/blog",
                snippet="Unverified opinion.",
                source_type="blog",
                verified=False,
            ),
        ],
        findings=[
            Finding(
                title="Pricing and packaging differ",
                summary="Cursor and Copilot expose different packaging signals.",
                evidence_ids=["cursor-pricing", "copilot-docs"],
            )
        ],
    )


def test_write_report_uses_llm_provider_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    messages: list[list[ChatMessage]] = []
    client = FakeLLMClient(
        content=(
            '{"markdown": "# InsightGraph Research Report\\n\\n'
            '**Research Request:** Compare Cursor and GitHub Copilot\\n\\n'
            '## Key Findings\\n\\n'
            '### Executive view\\n\\n'
            'Cursor and Copilot show distinct packaging signals for buyers. [1] [2]"}'
        ),
        messages=messages,
    )
    state = make_reporter_state()

    updated = write_report(state, llm_client=client)

    assert updated.report_markdown is not None
    assert "### Executive view" in updated.report_markdown
    assert "[1] Cursor Pricing. https://cursor.com/pricing" in updated.report_markdown
    assert "[2] GitHub Copilot Documentation. https://docs.github.com/en/copilot" in updated.report_markdown
    assert "https://example.com/blog" not in updated.report_markdown
    assert len(messages) == 1
    prompt = messages[0][1].content
    assert "Compare Cursor and GitHub Copilot" in prompt
    assert "Cursor Pricing" in prompt
    assert "unverified-blog" not in prompt


def test_write_report_strips_llm_references_and_appends_deterministic_references(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    client = FakeLLMClient(
        content=(
            '{"markdown": "# InsightGraph Research Report\\n\\n'
            '## Key Findings\\n\\n'
            'LLM body cites verified evidence. [1]\\n\\n'
            '## References\\n\\n'
            '[1] Fake Source. https://fake.example"}'
        )
    )
    state = make_reporter_state()

    updated = write_report(state, llm_client=client)

    assert updated.report_markdown is not None
    assert "https://fake.example" not in updated.report_markdown
    assert "[1] Cursor Pricing. https://cursor.com/pricing" in updated.report_markdown


@pytest.mark.parametrize(
    "content",
    [
        None,
        "not json",
        "{}",
        '{"markdown": ""}',
        '{"markdown": "## Key Findings\\n\\nFinding with no title. [1]"}',
        '{"markdown": "# InsightGraph Research Report\\n\\nNo findings heading. [1]"}',
        '{"markdown": "# InsightGraph Research Report\\n\\n## Key Findings\\n\\nIllegal citation. [99]"}',
        '{"markdown": "# InsightGraph Research Report\\n\\n## Key Findings\\n\\nNo citations here."}',
    ],
)
def test_write_report_falls_back_for_invalid_llm_output(monkeypatch, content: str | None) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    state = make_reporter_state()

    updated = write_report(state, llm_client=FakeLLMClient(content=content))

    assert updated.report_markdown is not None
    assert "### Pricing and packaging differ" in updated.report_markdown
    assert "### Executive view" not in updated.report_markdown


def test_write_report_falls_back_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    state = make_reporter_state()

    updated = write_report(state)

    assert updated.report_markdown is not None
    assert "### Pricing and packaging differ" in updated.report_markdown


def test_write_report_falls_back_for_llm_error(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    state = make_reporter_state()

    updated = write_report(state, llm_client=FakeLLMClient(error=RuntimeError("boom")))

    assert updated.report_markdown is not None
    assert "### Pricing and packaging differ" in updated.report_markdown


def test_write_report_does_not_fallback_for_unexpected_bug(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")

    def broken_build_messages(state, reference_numbers):
        raise TypeError("bug")

    monkeypatch.setattr(
        "insight_graph.agents.reporter._build_reporter_messages",
        broken_build_messages,
    )

    with pytest.raises(TypeError, match="bug"):
        write_report(make_reporter_state(), llm_client=FakeLLMClient(content='{"markdown": ""}'))
```

- [ ] **Step 2: Run LLM Reporter tests to verify they fail**

Run: `python -m pytest tests/test_agents.py::test_write_report_uses_llm_provider_when_enabled tests/test_agents.py::test_write_report_strips_llm_references_and_appends_deterministic_references tests/test_agents.py::test_write_report_falls_back_for_invalid_llm_output tests/test_agents.py::test_write_report_falls_back_without_api_key tests/test_agents.py::test_write_report_falls_back_for_llm_error tests/test_agents.py::test_write_report_does_not_fallback_for_unexpected_bug -v`

Expected: FAIL because `write_report()` does not yet accept `llm_client` and the LLM branch still returns deterministic output.

- [ ] **Step 3: Implement LLM Reporter**

Replace `src/insight_graph/agents/reporter.py` with:

```python
import json
import os
import re

from insight_graph.llm import ChatCompletionClient, ChatMessage, get_llm_client, resolve_llm_config
from insight_graph.state import Evidence, GraphState

CITATION_PATTERN = re.compile(r"\[(\d+)]")


def get_reporter_provider(name: str | None = None) -> str:
    provider = name or os.getenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "deterministic")
    if provider not in {"deterministic", "llm"}:
        raise ValueError(f"Unknown reporter provider: {provider}")
    return provider


def write_report(
    state: GraphState,
    llm_client: ChatCompletionClient | None = None,
) -> GraphState:
    provider = get_reporter_provider()
    if provider == "deterministic":
        return _write_report_deterministic(state)

    try:
        return _write_report_with_llm(state, llm_client=llm_client)
    except ValueError:
        return _write_report_deterministic(state)


def _write_report_deterministic(state: GraphState) -> GraphState:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    reference_numbers = _build_reference_numbers(verified_evidence)
    lines = [
        "# InsightGraph Research Report",
        "",
        f"**Research Request:** {state.user_request}",
        "",
        "## Key Findings",
        "",
    ]
    for finding in state.findings:
        citations = " ".join(
            f"[{reference_numbers[eid]}]"
            for eid in finding.evidence_ids
            if eid in reference_numbers
        )
        if not citations:
            continue
        lines.extend([f"### {finding.title}", "", f"{finding.summary} {citations}".strip(), ""])

    if state.critique is not None:
        lines.extend(_build_critic_assessment_section(state))

    lines.extend(_build_references_section(verified_evidence, reference_numbers))
    state.report_markdown = "\n".join(lines) + "\n"
    return state


def _write_report_with_llm(
    state: GraphState,
    llm_client: ChatCompletionClient | None = None,
) -> GraphState:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    reference_numbers = _build_reference_numbers(verified_evidence)
    if not reference_numbers:
        raise ValueError("Reporter requires verified evidence references.")

    if llm_client is None:
        config = resolve_llm_config()
        if not config.api_key:
            raise ValueError("LLM api_key is required")
        llm_client = get_llm_client(config)

    messages = _build_reporter_messages(state, reference_numbers)
    try:
        content = llm_client.complete_json(messages)
    except Exception as exc:
        raise ValueError("LLM reporter failed.") from exc

    body = _parse_llm_report_body(content)
    body = _strip_references_section(body)
    body = _validate_llm_report_body(body, set(reference_numbers.values()))
    lines = [body.rstrip(), ""]
    if state.critique is not None and "## Critic Assessment" not in body:
        lines.extend(_build_critic_assessment_section(state))
    lines.extend(_build_references_section(verified_evidence, reference_numbers))
    state.report_markdown = "\n".join(lines).rstrip() + "\n"
    return state


def _build_reporter_messages(
    state: GraphState,
    reference_numbers: dict[str, int],
) -> list[ChatMessage]:
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    evidence_lines = []
    for item in verified_evidence:
        evidence_lines.append(
            "\n".join(
                [
                    f"Reference [{reference_numbers[item.id]}]",
                    f"Evidence ID: {item.id}",
                    f"Title: {item.title}",
                    f"Source URL: {item.source_url}",
                    f"Source type: {item.source_type}",
                    f"Snippet: {item.snippet}",
                ]
            )
        )

    finding_lines = []
    for finding in state.findings:
        citations = " ".join(
            f"[{reference_numbers[evidence_id]}]"
            for evidence_id in finding.evidence_ids
            if evidence_id in reference_numbers
        )
        if not citations:
            continue
        finding_lines.append(
            "\n".join(
                [
                    f"Finding: {finding.title}",
                    f"Summary: {finding.summary}",
                    f"Allowed citations: {citations}",
                ]
            )
        )

    critique_text = state.critique.reason if state.critique is not None else "No critique available."
    prompt = "\n\n".join(
        [
            f"Research request: {state.user_request}",
            "Accepted findings:",
            "\n\n".join(finding_lines),
            "Verified evidence references:",
            "\n\n".join(evidence_lines),
            f"Critic assessment: {critique_text}",
            (
                "Return only JSON with a markdown string: "
                '{"markdown":"# InsightGraph Research Report\\n\\n..."}. '
                "The markdown must include # InsightGraph Research Report and ## Key Findings. "
                "Use only the allowed citation numbers like [1] or [1] [2]. "
                "Do not invent facts, URLs, or sources. Do not include a ## References section."
            ),
        ]
    )
    return [
        ChatMessage(
            role="system",
            content=(
                "You are a professional business intelligence report writer. "
                "Write concise, executive-ready Markdown grounded only in provided findings "
                "and verified evidence. Return JSON only."
            ),
        ),
        ChatMessage(role="user", content=prompt),
    ]


def _parse_llm_report_body(content: str | None) -> str:
    if not content:
        raise ValueError("LLM response content is required")
    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("LLM response must be valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")
    markdown = data.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError("LLM report markdown is required")
    return markdown


def _strip_references_section(markdown: str) -> str:
    marker = "\n## References"
    if marker in markdown:
        return markdown.split(marker, 1)[0].rstrip()
    if markdown.startswith("## References"):
        return ""
    return markdown.rstrip()


def _validate_llm_report_body(
    markdown: str,
    allowed_reference_numbers: set[int],
) -> str:
    if "# InsightGraph Research Report" not in markdown:
        raise ValueError("LLM report title is required")
    if "## Key Findings" not in markdown:
        raise ValueError("LLM report key findings section is required")
    citations = [int(match) for match in CITATION_PATTERN.findall(markdown)]
    if not citations:
        raise ValueError("LLM report must include at least one citation")
    if not set(citations).issubset(allowed_reference_numbers):
        raise ValueError("LLM report cites unknown references")
    return markdown.strip()


def _build_reference_numbers(verified_evidence: list[Evidence]) -> dict[str, int]:
    return {item.id: index for index, item in enumerate(verified_evidence, start=1)}


def _build_critic_assessment_section(state: GraphState) -> list[str]:
    if state.critique is None:
        return []
    return ["## Critic Assessment", "", state.critique.reason, ""]


def _build_references_section(
    verified_evidence: list[Evidence],
    reference_numbers: dict[str, int],
) -> list[str]:
    lines = ["## References", ""]
    for item in verified_evidence:
        number = reference_numbers[item.id]
        lines.append(f"[{number}] {item.title}. {item.source_url}")
    return lines
```

- [ ] **Step 4: Run LLM Reporter tests**

Run: `python -m pytest tests/test_agents.py::test_write_report_uses_llm_provider_when_enabled tests/test_agents.py::test_write_report_strips_llm_references_and_appends_deterministic_references tests/test_agents.py::test_write_report_falls_back_for_invalid_llm_output tests/test_agents.py::test_write_report_falls_back_without_api_key tests/test_agents.py::test_write_report_falls_back_for_llm_error tests/test_agents.py::test_write_report_does_not_fallback_for_unexpected_bug -v`

Expected: selected tests pass.

- [ ] **Step 5: Run agent, graph, and CLI tests**

Run: `python -m pytest tests/test_agents.py tests/test_graph.py tests/test_cli.py -v`

Expected: all selected tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/agents/reporter.py tests/test_agents.py
git commit -m "feat: add opt-in llm reporter"
```

---

### Task 3: Documentation And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README MVP table**

In `README.md`, after the Analyst row in the “当前 MVP 已实现” table, add:

```markdown
| Reporter | 默认 deterministic/offline；可通过 `INSIGHT_GRAPH_REPORTER_PROVIDER=llm` opt-in 使用 OpenAI-compatible LLM 生成更专业的报告正文，References 仍由系统基于 verified evidence 生成 |
```

- [ ] **Step 2: Update README MVP note**

Replace the sentence fragment:

```markdown
新闻/GitHub 专用搜索、FastAPI、PostgreSQL、pgvector、LLM 路由和可观测性属于后续路线图。
```

with:

```markdown
新闻/GitHub 专用搜索、FastAPI、PostgreSQL、pgvector、更完整的多 provider LLM 路由和可观测性属于后续路线图；当前已提供 OpenAI-compatible LLM 层供 Analyst/Reporter 等节点 opt-in 使用。
```

- [ ] **Step 3: Add LLM Reporter docs**

After the “### LLM Analyst 配置” section and its explanatory paragraph, add:

````markdown

### LLM Reporter 配置

Reporter 默认使用 deterministic/offline 逻辑，不调用真实 LLM。需要 OpenAI-compatible LLM 生成更专业的报告正文时，可显式 opt-in：

```bash
INSIGHT_GRAPH_REPORTER_PROVIDER=llm \
INSIGHT_GRAPH_LLM_API_KEY=sk-your-relay-key \
INSIGHT_GRAPH_LLM_BASE_URL=https://relay.example.com/v1 \
INSIGHT_GRAPH_LLM_MODEL=gpt-4o-mini \
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_REPORTER_PROVIDER` | Reporter provider 类型，支持默认离线行为的 `deterministic` 或 `llm` opt-in | `deterministic` |
| `INSIGHT_GRAPH_LLM_API_KEY` | OpenAI-compatible provider API key；未设置时回退到 `OPENAI_API_KEY` | - |
| `INSIGHT_GRAPH_LLM_BASE_URL` | OpenAI-compatible `/v1` endpoint；未设置时回退到 `OPENAI_BASE_URL` | - |
| `INSIGHT_GRAPH_LLM_MODEL` | OpenAI-compatible Reporter model | `gpt-4o-mini` |

LLM Reporter 只负责生成报告正文。最终 `## References` 由系统根据当前 verified evidence 重建；LLM 输出中的 fake References 会被丢弃，非法 citation 会触发 fallback 到 deterministic Reporter。测试不调用外部 LLM。
````

- [ ] **Step 4: Run documentation checks**

Run: `python -m pytest tests/test_cli.py -v`

Expected: CLI test passes.

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 5: Run final verification**

Run: `python -m pytest -v`

Expected: all tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

Run: `python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"`

Expected: output includes `# InsightGraph Research Report`, `## Key Findings`, and `## References`. Do not set `INSIGHT_GRAPH_REPORTER_PROVIDER=llm` for this smoke test.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: document llm reporter provider"
```

---

## Self-Review

- Spec coverage: This plan implements the LLM Reporter provider, deterministic default, shared LLM client reuse, citation guardrails, deterministic references, fallback behavior, README updates, and final verification.
- Deferred scope: Domain templates, streaming, chunking, budgets, tracing, persistence, and other agent changes remain excluded.
- Placeholder scan: No placeholders remain; each task includes exact file paths, code, commands, expected failures, expected passing checks, and commit messages.
- Type consistency: `get_reporter_provider`, `write_report`, `ChatCompletionClient`, `ChatMessage`, `INSIGHT_GRAPH_REPORTER_PROVIDER`, and helper names are consistent across tests, implementation, and docs.
