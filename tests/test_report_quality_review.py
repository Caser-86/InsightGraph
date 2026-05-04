from insight_graph.report_quality.report_review import (
    build_report_quality_review,
    format_report_quality_diagnostics,
)
from insight_graph.state import CompetitiveMatrixRow, Evidence, Finding, GraphState


def make_quality_state() -> GraphState:
    return GraphState(
        user_request="Compare Cursor and GitHub Copilot",
        evidence_pool=[
            Evidence(
                id="cursor",
                subtask_id="collect",
                title="Cursor Pricing",
                source_url="https://cursor.com/pricing",
                snippet="Cursor lists pricing tiers.",
                source_type="official_site",
                verified=True,
            ),
            Evidence(
                id="copilot",
                subtask_id="collect",
                title="GitHub Copilot Docs",
                source_url="https://docs.github.com/copilot",
                snippet="GitHub Copilot documentation describes features.",
                source_type="docs",
                verified=True,
            ),
            Evidence(
                id="news",
                subtask_id="collect",
                title="Market News",
                source_url="https://example.com/news",
                snippet="Market news discusses adoption.",
                source_type="news",
                verified=True,
            ),
        ],
        findings=[
            Finding(
                title="Packaging differs",
                summary="Cursor and Copilot show different packaging signals.",
                evidence_ids=["cursor", "copilot"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Cursor",
                positioning="Official pricing signal",
                strengths=["Clear packaging"],
                evidence_ids=["cursor"],
            )
        ],
        citation_support=[
            {
                "claim": "Packaging differs",
                "support_status": "supported",
                "evidence_ids": ["cursor", "copilot"],
            }
        ],
    )


def test_quality_review_scores_strong_report() -> None:
    state = make_quality_state()
    report = """# InsightGraph 深度研究报告

## 摘要

Cursor 和 GitHub Copilot 的包装信号不同 [1]。

## 背景

本报告基于官方和文档证据。

## 核心发现

Cursor 发布价格信号，Copilot 发布功能文档 [1] [2]。

## 证据分析

官方、文档和新闻来源形成交叉验证 [1] [2] [3]。

## 竞争格局

两者定位存在差异 [1] [2]。

## 趋势判断

市场采用仍需要持续跟踪 [3]。

## 风险

价格和产品策略可能变化。

## 结论

现有证据足以支持初步判断。
"""

    review = build_report_quality_review(state, report, intensity="standard")

    assert review["score"] >= 80
    assert review["status"] == "pass"
    assert review["metrics"]["verified_evidence_count"] == 3
    assert review["metrics"]["unique_source_type_count"] == 3


def test_quality_review_finds_weak_sections_and_actions() -> None:
    state = GraphState(user_request="Unknown market", report_markdown="# R\n")

    review = build_report_quality_review(state, "# InsightGraph 深度研究报告\n")

    assert review["score"] < 80
    assert review["status"] == "needs_improvement"
    assert "补充已验证证据" in " ".join(review["recommended_actions"])
    assert review["gaps"]


def test_quality_diagnostics_markdown_is_chinese_summary() -> None:
    review = build_report_quality_review(make_quality_state(), "# InsightGraph 深度研究报告\n")

    lines = format_report_quality_diagnostics(review)

    assert lines[0] == "## 报告质量诊断"
    assert any("综合评分" in line for line in lines)
    assert any("报告强度" in line for line in lines)
