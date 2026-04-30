from pathlib import Path


def test_gitignore_excludes_local_tool_caches_and_generated_eval_reports() -> None:
    gitignore = (Path(__file__).parents[1] / ".gitignore").read_text(encoding="utf-8")

    assert ".ruff_cache/" in gitignore
    assert "reports/eval.json" in gitignore
    assert "reports/eval.md" in gitignore
    assert "reports/eval-summary.json" in gitignore
    assert "reports/eval-summary.md" in gitignore
    assert "reports/eval-history.json" in gitignore
    assert "reports/eval-history.md" in gitignore
    assert "reports/ai-coding-agents-technical-review.md" in gitignore


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


def test_final_docs_align_to_live_research_product_path() -> None:
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
    assert "The next optimization goal" in combined
    assert "The active project route is now `docs/report-quality-roadmap.md`" not in docs[
        "roadmap"
    ]
    assert "Need reference-style live benchmark profile" not in docs["reference"]
    assert "Memory-on/off quality eval proof" not in docs["reference"]


def test_docs_define_high_quality_report_roadmap_and_defer_high_risk_items() -> None:
    root = Path(__file__).parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    roadmap = (root / "docs" / "roadmap.md").read_text(encoding="utf-8")
    architecture = (root / "docs" / "architecture.md").read_text(encoding="utf-8")
    combined = "\n".join([readme, roadmap, architecture])

    assert "生成高质量、可验证深度研究报告" in combined
    assert "Next Optimization Plan" in roadmap
    assert "Report Quality v3" in roadmap
    assert "Live Benchmark Case Profiles" in roadmap
    assert "Production RAG Hardening" in roadmap
    assert "Memory Quality Loop" in roadmap
    assert "Dashboard Productization" in roadmap
    assert "Deferred Until Other Optimizations Are Complete" in roadmap
    for item in [
        "MCP runtime invocation behind allowlist",
        "Real sandboxed Python/code execution",
        "`/tasks` API compatibility aliases",
        "release/deploy/force-push automation",
    ]:
        assert item in roadmap


def test_readme_uses_reference_style_sections_with_current_project_truths() -> None:
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

    expected_sections = [
        "## 项目结构",
        "## 核心特性",
        "## 技术架构",
        "## 整体执行流程",
        "## 多智能体协作流程",
        "## 数据流与证据链路",
        "## 技术栈",
        "## 内置工具",
        "## 执行链路详解",
        "## 示例输出",
        "## 效果与亮点",
        "## 快速开始",
        "## 配置说明",
        "## 脚本",
    ]
    for section in expected_sections:
        assert section in readme
    assert "Planner → Collector/Executor → Analyst → Critic → Reporter" in readme
    assert "Offline deterministic 是测试/CI fallback" in readme
    assert "真实 sandboxed Python/code execution 暂不启用" in readme
    assert "MCP runtime invocation 暂不启用" in readme
