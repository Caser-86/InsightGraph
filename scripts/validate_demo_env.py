#!/usr/bin/env python
"""InsightGraph 演示环境验证脚本。

读取 .env 或当前环境变量，检查关键配置是否正确设置。
输出 JSON 格式结果，任何 FAIL 项都会导致非零退出码。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def check(ok: bool, label: str, severity: str = "ERROR") -> dict[str, str]:
    return {
        "label": label,
        "status": "PASS" if ok else "FAIL",
        "severity": severity,
    }


def main() -> int:
    results: list[dict[str, str]] = []
    warnings: list[str] = []

    # ---- API 安全 ----
    api_key = env("INSIGHT_GRAPH_API_KEY")
    if api_key:
        results.append(check(len(api_key) >= 16, "API key 已设置且长度 >= 16"))
    else:
        warnings.append("API key 未设置：Dashboard 将公开所有接口")

    # ---- LLM 配置 ----
    llm_base = env("INSIGHT_GRAPH_LLM_BASE_URL")
    llm_key = env("INSIGHT_GRAPH_LLM_API_KEY")
    llm_model = env("INSIGHT_GRAPH_LLM_MODEL")

    results.append(check(bool(llm_base), "INSIGHT_GRAPH_LLM_BASE_URL 已设置"))
    results.append(check(bool(llm_key), "INSIGHT_GRAPH_LLM_API_KEY 已设置"))
    results.append(check(bool(llm_model), "INSIGHT_GRAPH_LLM_MODEL 已设置"))

    if not any([llm_base, llm_key, llm_model]):
        warnings.append("LLM 配置不完整：无法调用 LLM")

    # ---- LLM 路由 ----
    fast_model = env("INSIGHT_GRAPH_LLM_MODEL_FAST")
    default_model = env("INSIGHT_GRAPH_LLM_MODEL_DEFAULT")
    strong_model = env("INSIGHT_GRAPH_LLM_MODEL_STRONG")
    results.append(check(bool(fast_model), "快速模型 (FAST) 已设置"))
    results.append(check(bool(default_model), "默认模型 (DEFAULT) 已设置"))
    results.append(check(bool(strong_model), "强力模型 (STRONG) 已设置"))

    # ---- 搜索 ----
    search_provider = env("INSIGHT_GRAPH_SEARCH_PROVIDER", "duckduckgo")
    serpapi_key = env("INSIGHT_GRAPH_SERPAPI_KEY")

    if search_provider == "serpapi":
        results.append(check(bool(serpapi_key), "SerpAPI 已启用，key 必须设置"))
    elif search_provider == "duckduckgo":
        results.append(check(True, "搜索提供者: DuckDuckGo（无需 key）"))
    else:
        results.append(check(True, f"搜索提供者: {search_provider}"))

    if serpapi_key and search_provider != "serpapi":
        warnings.append("SerpAPI key 已设置但未启用为搜索提供者，可节省成本")

    # ---- SQLite ----
    sqlite_path = env("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", "data/research_jobs.db")
    sqlite_dir = Path(sqlite_path).parent
    writable = False
    try:
        sqlite_dir.mkdir(parents=True, exist_ok=True)
        test_file = sqlite_dir / ".insightgraph_write_test"
        test_file.write_text("test")
        test_file.unlink()
        writable = True
    except (OSError, PermissionError):
        pass
    results.append(check(writable, f"SQLite 数据目录可写: {sqlite_dir}"))

    # ---- 质量门控 ----
    results.append(check(
        bool(env("INSIGHT_GRAPH_MIN_SUCCESS_EVIDENCE")),
        "INSIGHT_GRAPH_MIN_SUCCESS_EVIDENCE 已设置",
    ))
    results.append(check(
        bool(env("INSIGHT_GRAPH_MIN_SUCCESS_VERIFIED_EVIDENCE")),
        "INSIGHT_GRAPH_MIN_SUCCESS_VERIFIED_EVIDENCE 已设置",
    ))

    # ---- 密钥安全 ----
    _placeholder_keys = {
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_SERPAPI_KEY",
        "INSIGHT_GRAPH_API_KEY",
    }
    _placeholder_values = {
        "replace-me",
        "replace-me-with-strong-random-key",
        "sk-your-deepseek-api-key",
    }
    for key_name in _placeholder_keys:
        key_val = env(key_name)
        if key_val and key_val in _placeholder_values:
            results.append(
                check(False, f"{key_name} 仍为占位符值", severity="WARN")
            )

    # ---- 报告强度 ----
    intensity = env("INSIGHT_GRAPH_REPORT_INTENSITY", "standard")
    results.append(check(
        intensity in ("concise", "standard", "deep", "deep-plus"),
        f"报告强度: {intensity}",
    ))

    # ---- 输出 ----
    output = {"results": results, "warnings": warnings}
    print(json.dumps(output, ensure_ascii=False, indent=2))

    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    warn_count = len(warnings)
    print(
        f"\n总计: {len(results)} 项, {fail_count} 失败, {warn_count} 警告",
        file=sys.stderr,
    )
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
