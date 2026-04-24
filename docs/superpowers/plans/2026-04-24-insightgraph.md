# InsightGraph MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable MVP of InsightGraph: a LangGraph-based multi-agent research workflow that accepts a research question, generates subtasks, collects mock evidence, analyzes it, critiques evidence sufficiency, and writes a cited Markdown report.

**Architecture:** Implement a Python package under `src/insight_graph` with focused modules for state, agents, graph assembly, tools, and CLI. The MVP uses deterministic local/mock tools first so tests do not require network or paid LLM access; LLM and real search adapters can be added after the graph contract is stable.

**Tech Stack:** Python 3.11+, LangGraph, LangChain Core, Pydantic, Typer, Pytest, Ruff.

---

## Scope

This plan implements the first working vertical slice only:

- CLI command: `insight-graph research "..."`
- LangGraph nodes: Planner, Collector, Analyst, Critic, Reporter
- Typed graph state and evidence models
- Deterministic mock evidence collection
- Citation-aware Markdown report generation
- Tests for state models, each agent, graph execution, and CLI smoke behavior

This plan intentionally does not implement FastAPI, PostgreSQL, pgvector, real web search, GitHub search, Playwright, or persistent checkpoints. Those are separate follow-up plans after the graph MVP is testable.

## File Structure

- Create: `pyproject.toml` - package metadata, dependencies, CLI entrypoint, test/lint config.
- Create: `src/insight_graph/__init__.py` - package version.
- Create: `src/insight_graph/state.py` - Pydantic models for subtasks, evidence, analysis, critique, and graph state.
- Create: `src/insight_graph/agents/planner.py` - deterministic task planner.
- Create: `src/insight_graph/agents/collector.py` - evidence collection node using a tool registry.
- Create: `src/insight_graph/agents/analyst.py` - analysis node that builds findings and competitive matrix rows.
- Create: `src/insight_graph/agents/critic.py` - critique node that decides pass/replan based on evidence coverage.
- Create: `src/insight_graph/agents/reporter.py` - Markdown report node.
- Create: `src/insight_graph/agents/__init__.py` - agent exports.
- Create: `src/insight_graph/tools/mock_search.py` - deterministic mock search/fetch data.
- Create: `src/insight_graph/tools/registry.py` - minimal tool registry abstraction.
- Create: `src/insight_graph/tools/__init__.py` - tool exports.
- Create: `src/insight_graph/graph.py` - LangGraph StateGraph assembly and runner.
- Create: `src/insight_graph/cli.py` - Typer CLI entrypoint.
- Create: `tests/test_state.py` - model tests.
- Create: `tests/test_agents.py` - node tests.
- Create: `tests/test_graph.py` - graph integration test.
- Create: `tests/test_cli.py` - CLI smoke test.

---

### Task 1: Project Skeleton And Tooling

**Files:**
- Create: `pyproject.toml`
- Create: `src/insight_graph/__init__.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Create package metadata**

Create `pyproject.toml`:

```toml
[project]
name = "insightgraph"
version = "0.1.0"
description = "LangGraph-based multi-agent business intelligence research engine"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "langgraph>=0.2.0",
  "langchain-core>=0.3.0",
  "pydantic>=2.7.0",
  "typer>=0.12.0",
  "rich>=13.7.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0",
  "ruff>=0.5.0",
]

[project.scripts]
insight-graph = "insight_graph.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/insight_graph"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 2: Create package init**

Create `src/insight_graph/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Write initial package test**

Create `tests/test_state.py` with this initial smoke test:

```python
from insight_graph import __version__


def test_package_version_is_defined() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state.py -v`

Expected: `1 passed`.

- [ ] **Step 5: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/insight_graph/__init__.py tests/test_state.py
git commit -m "chore: add Python project skeleton"
```

---

### Task 2: Typed Research State

**Files:**
- Create: `src/insight_graph/state.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Write failing state model tests**

Replace `tests/test_state.py` with:

```python
from insight_graph import __version__
from insight_graph.state import Evidence, GraphState, Subtask


def test_package_version_is_defined() -> None:
    assert __version__ == "0.1.0"


def test_subtask_defaults_to_research_type() -> None:
    subtask = Subtask(id="s1", description="Compare Cursor and GitHub Copilot")

    assert subtask.subtask_type == "research"
    assert subtask.dependencies == []
    assert subtask.suggested_tools == []


def test_evidence_requires_source_url() -> None:
    evidence = Evidence(
        id="e1",
        subtask_id="s1",
        title="Cursor pricing",
        source_url="https://cursor.com/pricing",
        snippet="Cursor publishes pricing tiers on its pricing page.",
        source_type="official_site",
    )

    assert evidence.verified is False
    assert evidence.source_domain == "cursor.com"


def test_graph_state_starts_with_empty_collections() -> None:
    state = GraphState(user_request="Analyze AI coding agents")

    assert state.user_request == "Analyze AI coding agents"
    assert state.subtasks == []
    assert state.evidence_pool == []
    assert state.findings == []
    assert state.report_markdown is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.state'`.

- [ ] **Step 3: Implement state models**

Create `src/insight_graph/state.py`:

```python
from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field


SubtaskType = Literal["research", "company", "product", "market", "technology", "synthesis"]
SourceType = Literal["official_site", "docs", "github", "news", "blog", "unknown"]


class Subtask(BaseModel):
    id: str
    description: str
    subtask_type: SubtaskType = "research"
    dependencies: list[str] = Field(default_factory=list)
    suggested_tools: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    id: str
    subtask_id: str
    title: str
    source_url: str
    snippet: str
    source_type: SourceType = "unknown"
    verified: bool = False

    @property
    def source_domain(self) -> str:
        return urlparse(self.source_url).netloc.lower()


class Finding(BaseModel):
    title: str
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)


class Critique(BaseModel):
    passed: bool
    reason: str
    missing_topics: list[str] = Field(default_factory=list)


class GraphState(BaseModel):
    user_request: str
    subtasks: list[Subtask] = Field(default_factory=list)
    evidence_pool: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    critique: Critique | None = None
    report_markdown: str | None = None
    iterations: int = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/insight_graph/state.py tests/test_state.py
git commit -m "feat: add typed research state models"
```

---

### Task 3: Planner Agent

**Files:**
- Create: `src/insight_graph/agents/__init__.py`
- Create: `src/insight_graph/agents/planner.py`
- Create: `tests/test_agents.py`

- [ ] **Step 1: Write failing planner test**

Create `tests/test_agents.py`:

```python
from insight_graph.agents.planner import plan_research
from insight_graph.state import GraphState


def test_planner_creates_core_research_subtasks() -> None:
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    descriptions = [task.description for task in updated.subtasks]
    assert len(updated.subtasks) == 4
    assert descriptions == [
        "Identify key products, companies, and scope from the user request",
        "Collect evidence about product positioning, features, pricing, and sources",
        "Analyze competitive patterns, differentiators, risks, and trends",
        "Synthesize findings into a cited research report",
    ]
    assert updated.subtasks[1].suggested_tools == ["mock_search"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py::test_planner_creates_core_research_subtasks -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.agents'`.

- [ ] **Step 3: Implement planner**

Create `src/insight_graph/agents/__init__.py`:

```python
from insight_graph.agents.planner import plan_research

__all__ = ["plan_research"]
```

Create `src/insight_graph/agents/planner.py`:

```python
from insight_graph.state import GraphState, Subtask


def plan_research(state: GraphState) -> GraphState:
    state.subtasks = [
        Subtask(
            id="scope",
            description="Identify key products, companies, and scope from the user request",
            subtask_type="research",
        ),
        Subtask(
            id="collect",
            description="Collect evidence about product positioning, features, pricing, and sources",
            subtask_type="research",
            dependencies=["scope"],
            suggested_tools=["mock_search"],
        ),
        Subtask(
            id="analyze",
            description="Analyze competitive patterns, differentiators, risks, and trends",
            subtask_type="synthesis",
            dependencies=["collect"],
        ),
        Subtask(
            id="report",
            description="Synthesize findings into a cited research report",
            subtask_type="synthesis",
            dependencies=["analyze"],
        ),
    ]
    return state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agents.py::test_planner_creates_core_research_subtasks -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/insight_graph/agents tests/test_agents.py
git commit -m "feat: add deterministic research planner"
```

---

### Task 4: Mock Tool Registry And Collector

**Files:**
- Create: `src/insight_graph/tools/__init__.py`
- Create: `src/insight_graph/tools/mock_search.py`
- Create: `src/insight_graph/tools/registry.py`
- Create: `src/insight_graph/agents/collector.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Add failing collector test**

Append to `tests/test_agents.py`:

```python
from insight_graph.agents.collector import collect_evidence


def test_collector_adds_verified_mock_evidence() -> None:
    state = GraphState(user_request="Compare Cursor and GitHub Copilot")
    state = plan_research(state)

    updated = collect_evidence(state)

    assert len(updated.evidence_pool) >= 3
    assert all(item.verified for item in updated.evidence_pool)
    assert {item.source_type for item in updated.evidence_pool} >= {"official_site", "github"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py::test_collector_adds_verified_mock_evidence -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.agents.collector'`.

- [ ] **Step 3: Implement mock search data**

Create `src/insight_graph/tools/mock_search.py`:

```python
from insight_graph.state import Evidence


def mock_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    return [
        Evidence(
            id="cursor-pricing",
            subtask_id=subtask_id,
            title="Cursor Pricing",
            source_url="https://cursor.com/pricing",
            snippet="Cursor publishes product tiers and pricing on its official pricing page.",
            source_type="official_site",
            verified=True,
        ),
        Evidence(
            id="github-copilot-docs",
            subtask_id=subtask_id,
            title="GitHub Copilot Documentation",
            source_url="https://docs.github.com/copilot",
            snippet="GitHub Copilot documentation describes IDE integrations and enterprise features.",
            source_type="docs",
            verified=True,
        ),
        Evidence(
            id="opencode-github",
            subtask_id=subtask_id,
            title="OpenCode Repository",
            source_url="https://github.com/sst/opencode",
            snippet="The OpenCode repository provides public project information, README content, and release history.",
            source_type="github",
            verified=True,
        ),
    ]
```

- [ ] **Step 4: Implement tool registry**

Create `src/insight_graph/tools/registry.py`:

```python
from collections.abc import Callable

from insight_graph.state import Evidence
from insight_graph.tools.mock_search import mock_search


ToolFn = Callable[[str, str], list[Evidence]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {"mock_search": mock_search}

    def run(self, name: str, query: str, subtask_id: str) -> list[Evidence]:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name](query, subtask_id)
```

Create `src/insight_graph/tools/__init__.py`:

```python
from insight_graph.tools.registry import ToolRegistry

__all__ = ["ToolRegistry"]
```

- [ ] **Step 5: Implement collector**

Create `src/insight_graph/agents/collector.py`:

```python
from insight_graph.state import GraphState
from insight_graph.tools import ToolRegistry


def collect_evidence(state: GraphState) -> GraphState:
    registry = ToolRegistry()
    collected = []
    for subtask in state.subtasks:
        for tool_name in subtask.suggested_tools:
            collected.extend(registry.run(tool_name, state.user_request, subtask.id))
    state.evidence_pool = collected
    return state
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_agents.py::test_collector_adds_verified_mock_evidence -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/insight_graph/tools src/insight_graph/agents/collector.py tests/test_agents.py
git commit -m "feat: add mock evidence collector"
```

---

### Task 5: Analyst, Critic, And Reporter

**Files:**
- Create: `src/insight_graph/agents/analyst.py`
- Create: `src/insight_graph/agents/critic.py`
- Create: `src/insight_graph/agents/reporter.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Add failing analysis pipeline test**

Append to `tests/test_agents.py`:

```python
from insight_graph.agents.analyst import analyze_evidence
from insight_graph.agents.critic import critique_analysis
from insight_graph.agents.reporter import write_report


def test_analysis_critic_and_reporter_create_cited_report() -> None:
    state = GraphState(user_request="Compare AI coding agents")
    state = collect_evidence(plan_research(state))

    state = analyze_evidence(state)
    state = critique_analysis(state)
    state = write_report(state)

    assert len(state.findings) == 2
    assert state.critique is not None
    assert state.critique.passed is True
    assert state.report_markdown is not None
    assert "# InsightGraph Research Report" in state.report_markdown
    assert "## References" in state.report_markdown
    assert "[1]" in state.report_markdown
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py::test_analysis_critic_and_reporter_create_cited_report -v`

Expected: FAIL with missing analyst module.

- [ ] **Step 3: Implement analyst**

Create `src/insight_graph/agents/analyst.py`:

```python
from insight_graph.state import Finding, GraphState


def analyze_evidence(state: GraphState) -> GraphState:
    evidence_ids = [item.id for item in state.evidence_pool]
    state.findings = [
        Finding(
            title="Official sources establish baseline product positioning",
            summary="Official pricing pages, documentation, and repositories provide the safest baseline for comparing product positioning and capabilities.",
            evidence_ids=evidence_ids[:2],
        ),
        Finding(
            title="Open repositories add adoption and roadmap signals",
            summary="GitHub evidence helps evaluate public development activity, release cadence, and community-facing positioning.",
            evidence_ids=evidence_ids[2:],
        ),
    ]
    return state
```

- [ ] **Step 4: Implement critic**

Create `src/insight_graph/agents/critic.py`:

```python
from insight_graph.state import Critique, GraphState


def critique_analysis(state: GraphState) -> GraphState:
    verified_count = sum(1 for item in state.evidence_pool if item.verified)
    has_findings = bool(state.findings)
    passed = verified_count >= 3 and has_findings
    state.critique = Critique(
        passed=passed,
        reason="Sufficient verified evidence and findings are available." if passed else "Evidence or findings are insufficient.",
        missing_topics=[] if passed else ["verified evidence", "analysis findings"],
    )
    return state
```

- [ ] **Step 5: Implement reporter**

Create `src/insight_graph/agents/reporter.py`:

```python
from insight_graph.state import GraphState


def write_report(state: GraphState) -> GraphState:
    reference_numbers = {item.id: index for index, item in enumerate(state.evidence_pool, start=1)}
    lines = [
        "# InsightGraph Research Report",
        "",
        f"**Research Request:** {state.user_request}",
        "",
        "## Key Findings",
        "",
    ]
    for finding in state.findings:
        citations = " ".join(f"[{reference_numbers[eid]}]" for eid in finding.evidence_ids if eid in reference_numbers)
        lines.extend([f"### {finding.title}", "", f"{finding.summary} {citations}".strip(), ""])

    if state.critique is not None:
        lines.extend(["## Critic Assessment", "", state.critique.reason, ""])

    lines.extend(["## References", ""])
    for item in state.evidence_pool:
        number = reference_numbers[item.id]
        lines.append(f"[{number}] {item.title}. {item.source_url}")

    state.report_markdown = "\n".join(lines) + "\n"
    return state
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_agents.py -v`

Expected: all agent tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/insight_graph/agents tests/test_agents.py
git commit -m "feat: add analysis critique and reporting agents"
```

---

### Task 6: LangGraph Assembly

**Files:**
- Create: `src/insight_graph/graph.py`
- Create: `tests/test_graph.py`

- [ ] **Step 1: Write failing graph integration test**

Create `tests/test_graph.py`:

```python
from insight_graph.graph import run_research


def test_run_research_executes_full_graph() -> None:
    result = run_research("Compare Cursor, OpenCode, and GitHub Copilot")

    assert result.critique is not None
    assert result.critique.passed is True
    assert result.report_markdown is not None
    assert "# InsightGraph Research Report" in result.report_markdown
    assert "https://cursor.com/pricing" in result.report_markdown
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_graph.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.graph'`.

- [ ] **Step 3: Implement graph**

Create `src/insight_graph/graph.py`:

```python
from langgraph.graph import END, StateGraph

from insight_graph.agents.analyst import analyze_evidence
from insight_graph.agents.collector import collect_evidence
from insight_graph.agents.critic import critique_analysis
from insight_graph.agents.planner import plan_research
from insight_graph.agents.reporter import write_report
from insight_graph.state import GraphState


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("planner", plan_research)
    graph.add_node("collector", collect_evidence)
    graph.add_node("analyst", analyze_evidence)
    graph.add_node("critic", critique_analysis)
    graph.add_node("reporter", write_report)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "collector")
    graph.add_edge("collector", "analyst")
    graph.add_edge("analyst", "critic")
    graph.add_conditional_edges("critic", _route_after_critic, {"reporter": "reporter", "planner": "planner"})
    graph.add_edge("reporter", END)
    return graph.compile()


def _route_after_critic(state: GraphState) -> str:
    if state.critique is not None and state.critique.passed:
        return "reporter"
    if state.iterations >= 1:
        return "reporter"
    state.iterations += 1
    return "planner"


def run_research(user_request: str) -> GraphState:
    compiled = build_graph()
    result = compiled.invoke(GraphState(user_request=user_request))
    if isinstance(result, GraphState):
        return result
    return GraphState.model_validate(result)
```

- [ ] **Step 4: Run graph test**

Run: `python -m pytest tests/test_graph.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/insight_graph/graph.py tests/test_graph.py
git commit -m "feat: assemble LangGraph research workflow"
```

---

### Task 7: CLI Entrypoint

**Files:**
- Create: `src/insight_graph/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI smoke test**

Create `tests/test_cli.py`:

```python
from typer.testing import CliRunner

from insight_graph.cli import app


def test_cli_research_outputs_markdown_report() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents"])

    assert result.exit_code == 0
    assert "# InsightGraph Research Report" in result.output
    assert "## References" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.cli'`.

- [ ] **Step 3: Implement CLI**

Create `src/insight_graph/cli.py`:

```python
import typer

from insight_graph.graph import run_research

app = typer.Typer(help="InsightGraph research workflow CLI")


@app.command()
def research(query: str) -> None:
    """Run a research workflow and print a Markdown report."""
    state = run_research(query)
    typer.echo(state.report_markdown or "")
```

- [ ] **Step 4: Run CLI test**

Run: `python -m pytest tests/test_cli.py -v`

Expected: PASS.

- [ ] **Step 5: Run installed command manually**

Run: `python -m insight_graph.cli research "Compare AI coding agents"`

Expected: command may fail because Typer apps are not invoked automatically by `python -m` unless module main handling is added.

- [ ] **Step 6: Add module main support**

Append this to `src/insight_graph/cli.py`:

```python

if __name__ == "__main__":
    app()
```

- [ ] **Step 7: Run module command again**

Run: `python -m insight_graph.cli research "Compare AI coding agents"`

Expected: output includes `# InsightGraph Research Report` and `## References`.

- [ ] **Step 8: Commit**

```bash
git add src/insight_graph/cli.py tests/test_cli.py
git commit -m "feat: add research CLI"
```

---

### Task 8: Final Verification And README Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README quick start repository URL**

Change the clone example in `README.md` from:

```bash
git clone https://github.com/your-org/insightgraph.git
cd insightgraph
```

to:

```bash
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph
```

- [ ] **Step 2: Add MVP status note near the top of README**

Add this paragraph after the opening description:

```markdown
> 当前仓库处于 MVP 架构落地阶段：优先实现可测试的 LangGraph 多智能体研究流骨架，再逐步接入真实搜索、持久化、向量记忆与 Web API。
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest -v`

Expected: all tests pass.

- [ ] **Step 4: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 5: Run CLI smoke command**

Run: `python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"`

Expected: output includes `# InsightGraph Research Report`, `## Key Findings`, and `## References`.

- [ ] **Step 6: Commit README and final cleanup**

```bash
git add README.md
git commit -m "docs: document MVP implementation status"
```

- [ ] **Step 7: Push all commits**

```bash
git push
```

Expected: push succeeds to `origin/master`.

---

## Self-Review

- Spec coverage: This plan covers the README's core MVP architecture: Planner, Collector, Analyst, Critic, Reporter, evidence pool, citation-aware report, CLI, and testable graph execution.
- Deferred scope: FastAPI, WebSocket, PostgreSQL, pgvector, real web/news/GitHub search, Playwright, and observability are explicitly excluded from this MVP and should get separate plans.
- Placeholder scan: No implementation step relies on TBD values; every file and command is specified.
- Type consistency: The plan consistently uses `GraphState`, `Subtask`, `Evidence`, `Finding`, `Critique`, `plan_research`, `collect_evidence`, `analyze_evidence`, `critique_analysis`, `write_report`, and `run_research`.
