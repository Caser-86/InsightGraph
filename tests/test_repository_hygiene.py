from pathlib import Path


def test_gitignore_excludes_local_runtime_noise() -> None:
    gitignore = (Path(__file__).parents[1] / ".gitignore").read_text(encoding="utf-8")

    for token in [
        ".ruff_cache/",
        ".pytest_cache/",
        "reports/eval.json",
        "reports/eval.md",
        "reports/eval-summary.json",
        "reports/eval-summary.md",
        "reports/eval-history.json",
        "reports/eval-history.md",
        "reports/ai-coding-agents-technical-review.md",
        "debug.log",
        "error.log",
        "data/",
    ]:
        assert token in gitignore


def test_report_quality_roadmap_documents_worktree_pythonpath_rule() -> None:
    roadmap = (Path(__file__).parents[1] / "docs" / "report-quality-roadmap.md").read_text(
        encoding="utf-8"
    )

    assert "PYTHONPATH=src" in roadmap
    assert "worktree" in roadmap.lower()
    assert "editable install" in roadmap


def test_historical_superpowers_process_docs_are_not_tracked() -> None:
    root = Path(__file__).parents[1]

    plan_files = sorted((root / "docs" / "superpowers" / "plans").glob("*.md"))
    spec_dir = root / "docs" / "superpowers" / "specs"

    assert [path.name for path in plan_files] == [
        "2026-04-30-remaining-product-roadmap.md"
    ]
    assert not spec_dir.exists()


def test_generated_showcase_report_is_not_tracked() -> None:
    root = Path(__file__).parents[1]
    assert not (root / "reports" / "ai-coding-agents-technical-review.md").exists()


def test_live_benchmark_is_documented_as_manual_opt_in() -> None:
    root = Path(__file__).parents[1]
    docs = "\n".join(
        [
            (root / "README.md").read_text(encoding="utf-8"),
            (root / "docs" / "scripts.md").read_text(encoding="utf-8"),
            (root / "docs" / "configuration.md").read_text(encoding="utf-8"),
        ]
    )

    assert "scripts/benchmark_live_research.py" in docs
    assert "--allow-live" in docs
    assert "INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1" in docs
    assert "network/LLM cost" in docs
    assert "live-research" in docs


def test_live_benchmark_artifacts_and_case_profiles_are_documented() -> None:
    root = Path(__file__).parents[1]
    docs = "\n".join(
        [
            (root / "README.md").read_text(encoding="utf-8"),
            (root / "docs" / "scripts.md").read_text(encoding="utf-8"),
            (root / "docs" / "configuration.md").read_text(encoding="utf-8"),
        ]
    )

    assert "docs/benchmarks/live-research-cases.json" in docs
    assert "--case-file docs/benchmarks/live-research-cases.json" in docs
    for field in [
        "url_validation_rate",
        "citation_precision_proxy",
        "source_diversity_by_type",
        "source_diversity_by_domain",
        "section_coverage",
        "total_tokens",
    ]:
        assert field in docs
    assert "Do not commit generated live benchmark reports" in docs


def test_docs_align_to_live_research_product_path() -> None:
    root = Path(__file__).parents[1]
    docs = {
        "roadmap": (root / "docs" / "roadmap.md").read_text(encoding="utf-8"),
        "architecture": (root / "docs" / "architecture.md").read_text(encoding="utf-8"),
        "reference": (root / "docs" / "reference-parity-roadmap.md").read_text(
            encoding="utf-8"
        ),
        "report_quality": (root / "docs" / "report-quality-roadmap.md").read_text(
            encoding="utf-8"
        ),
    }

    combined = "\n".join(docs.values())
    assert "product path is `live-research`" in combined
    assert "Offline remains the deterministic testing/CI fallback" in combined
    assert "high-quality, evidence-grounded" in combined
    assert "Need reference-style live benchmark profile" not in docs["reference"]
    assert "Memory-on/off quality eval proof" not in docs["reference"]


def test_docs_define_completed_route_and_deferred_items() -> None:
    root = Path(__file__).parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    roadmap = (root / "docs" / "roadmap.md").read_text(encoding="utf-8")
    architecture = (root / "docs" / "architecture.md").read_text(encoding="utf-8")
    combined = "\n".join([readme, roadmap, architecture])

    assert "Completed Optimization Batches" in roadmap
    assert "Report Quality v3 - complete" in roadmap
    assert "Live Benchmark Case Profiles - complete" in roadmap
    assert "Production RAG Hardening - complete" in roadmap
    assert "Memory Quality Loop - complete" in roadmap
    assert "Dashboard Productization - complete" in roadmap
    assert "API And Operations Hardening - complete" in roadmap
    assert "Remaining Explicit-Decision Work" in roadmap
    for item in [
        "MCP runtime invocation behind allowlist",
        "Real sandboxed Python/code execution",
        "`/tasks` API compatibility aliases",
        "release/deploy automation dry-run only",
    ]:
        assert item in combined


def test_readme_explains_layered_documentation_and_project_truths() -> None:
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

    for section in [
        "## What It Does",
        "## Product Truths",
        "## Architecture At A Glance",
        "## Quick Start",
        "## Documentation Guide",
        "## Runtime Diagnostics",
        "## Built-In Tools",
        "## Storage And Memory",
        "## Live Benchmark",
    ]:
        assert section in readme

    assert "English Reference Docs" in readme
    assert "Chinese Operator Docs" in readme
    assert "Internal Reference Docs" in readme
    assert "Planner -> Collector/Executor -> Analyst -> Critic -> Reporter" in readme
    assert "Offline remains the deterministic testing/CI fallback" in readme
    assert "Real sandboxed Python/code execution is not enabled." in readme
    assert "MCP runtime invocation is not enabled." in readme


def test_deployment_runbook_aligns_operational_env_surfaces() -> None:
    root = Path(__file__).parents[1]
    docs = {
        "README.md": (root / "README.md").read_text(encoding="utf-8"),
        "docs/deployment.md": (root / "docs" / "deployment.md").read_text(
            encoding="utf-8"
        ),
        "docs/configuration.md": (root / "docs" / "configuration.md").read_text(
            encoding="utf-8"
        ),
    }
    combined = "\n".join(docs.values())

    for token in [
        "INSIGHT_GRAPH_API_KEY",
        "INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite",
        "INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH",
        "INSIGHT_GRAPH_RESEARCH_JOBS_STARTUP_WORKER",
        "INSIGHT_GRAPH_RESEARCH_JOBS_TERMINAL_RETENTION_DAYS",
        "INSIGHT_GRAPH_CHECKPOINT_BACKEND=postgres",
        "INSIGHT_GRAPH_POSTGRES_DSN",
        "INSIGHT_GRAPH_MEMORY_BACKEND=pgvector",
        "INSIGHT_GRAPH_DOCUMENT_INDEX_BACKEND=pgvector",
        "INSIGHT_GRAPH_DOCUMENT_PGVECTOR_DSN",
        "INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo",
        "INSIGHT_GRAPH_GITHUB_PROVIDER=live",
        "INSIGHT_GRAPH_USE_SEC_FILINGS",
        "INSIGHT_GRAPH_LLM_TRACE",
        "INSIGHT_GRAPH_LLM_TRACE_PATH",
        "INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1",
    ]:
        assert token in combined

    assert "metadata-only" in combined
    assert "prompt/completion" in combined
    assert "Do not commit generated live benchmark reports" in combined
    assert "Trace Redaction" in docs["docs/deployment.md"]
    assert "Storage Matrix" in docs["docs/deployment.md"]


def test_roadmap_and_readme_mark_completed_batches_and_next_priorities() -> None:
    root = Path(__file__).parents[1]
    roadmap = (root / "docs" / "roadmap.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    combined = "\n".join([roadmap, readme])

    assert "## Completed Optimization Batches" in roadmap
    assert "## Remaining Explicit-Decision Work" in roadmap
    assert "A-F complete" in combined
    assert "Report Quality v3 - complete" in roadmap
    assert "API And Operations Hardening - complete" in roadmap
    assert "1. `/tasks` API compatibility aliases" in roadmap
    assert "2. MCP runtime invocation behind allowlist" in roadmap
    assert "3. release/deploy automation dry-run only" in roadmap
    assert "4. Real sandboxed Python/code execution" in roadmap
    assert "release/deploy/force-push automation" not in roadmap
    assert "Internal Reference Docs" in readme
