# Benchmark Research Script MVP 设计

## 目标

新增 `scripts/benchmark_research.py`，为当前 deterministic/offline 研究流提供可重复运行的基准脚本。脚本用于快速检查固定研究任务的结构化输出是否仍然完整，并记录基础耗时与计数指标。

第一版是离线 smoke benchmark，不是性能压测或 CI 阈值 gate。

## 非目标

- 不运行 live LLM preset。
- 不启用真实 web/news/github 搜索。
- 不访问公网。
- 不新增阈值判断或非零退出策略。
- 不写文件、不维护历史趋势。
- 不新增数据库、API 调用或后台任务。
- 不改变 `run_research()` 或 CLI 默认行为。

## 脚本入口

新增文件：

```text
scripts/benchmark_research.py
```

运行方式：

```bash
python scripts/benchmark_research.py
python scripts/benchmark_research.py --markdown
```

脚本应可从仓库根目录运行。第一版不需要 console script entry point。

## Benchmark Cases

内置固定 cases：

```python
BENCHMARK_CASES = [
    "Compare Cursor, OpenCode, and GitHub Copilot",
    "Analyze AI coding agents market positioning",
    "Compare Claude Code, Codeium, and Windsurf",
]
```

这些 case 必须使用默认 offline workflow。脚本在每个 case 前清理会改变默认工具/LLM行为的环境变量，确保不会因为用户 shell 中已有 opt-in env 而联网或调用 LLM。

需要清理的 env：

- `INSIGHT_GRAPH_ANALYST_PROVIDER`
- `INSIGHT_GRAPH_REPORTER_PROVIDER`
- `INSIGHT_GRAPH_LLM_API_KEY`
- `INSIGHT_GRAPH_LLM_BASE_URL`
- `INSIGHT_GRAPH_LLM_MODEL`
- `INSIGHT_GRAPH_USE_WEB_SEARCH`
- `INSIGHT_GRAPH_USE_GITHUB_SEARCH`
- `INSIGHT_GRAPH_USE_NEWS_SEARCH`
- `INSIGHT_GRAPH_USE_DOCUMENT_READER`
- `INSIGHT_GRAPH_USE_READ_FILE`
- `INSIGHT_GRAPH_USE_LIST_DIRECTORY`
- `INSIGHT_GRAPH_USE_WRITE_FILE`
- `INSIGHT_GRAPH_SEARCH_PROVIDER`
- `INSIGHT_GRAPH_RELEVANCE_FILTER`
- `INSIGHT_GRAPH_RELEVANCE_JUDGE`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`

环境清理应只影响脚本进程，不写入用户级或系统级环境变量。

## JSON 输出

默认输出 JSON 到 stdout。

Schema：

```json
{
  "cases": [
    {
      "query": "Compare Cursor, OpenCode, and GitHub Copilot",
      "duration_ms": 12,
      "finding_count": 2,
      "competitive_matrix_row_count": 3,
      "reference_count": 4,
      "tool_call_count": 4,
      "llm_call_count": 0,
      "critique_passed": true,
      "report_has_competitive_matrix": true
    }
  ],
  "summary": {
    "case_count": 3,
    "total_duration_ms": 36,
    "all_critique_passed": true,
    "total_findings": 6,
    "total_competitive_matrix_rows": 7,
    "total_references": 12,
    "total_tool_calls": 12,
    "total_llm_calls": 0
  }
}
```

字段定义：

- `duration_ms`: 单 case `run_research()` wall-clock 耗时，取整数毫秒。
- `finding_count`: `len(state.findings)`。
- `competitive_matrix_row_count`: `len(state.competitive_matrix)`。
- `reference_count`: `state.report_markdown` 中 References section 的条目数。第一版可用 `^\d+\. ` 或 `^- \[` 风格的简单 parser；如无法识别，返回 `0`。
- `tool_call_count`: `len(state.tool_call_log)`。
- `llm_call_count`: `len(state.llm_call_log)`，offline 预期为 `0`。
- `critique_passed`: `state.critique.passed`，无 critique 时为 `false`。
- `report_has_competitive_matrix`: report markdown 是否包含 `## Competitive Matrix`。

输出 JSON 使用 `indent=2` 和 `ensure_ascii=False`。

## Markdown 输出

`--markdown` 输出 GitHub-flavored Markdown 表格到 stdout，不同时输出 JSON。

格式：

```markdown
# InsightGraph Benchmark

| Query | Duration ms | Findings | Matrix rows | References | Tool calls | LLM calls | Critique passed | Matrix section |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Compare Cursor, OpenCode, and GitHub Copilot | 12 | 2 | 3 | 4 | 4 | 0 | true | true |

## Summary

| Cases | Total duration ms | All critique passed | Total findings | Total matrix rows | Total references | Total tool calls | Total LLM calls |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 3 | 36 | true | 6 | 7 | 12 | 12 | 0 |
```

Markdown table cells must escape `|` and compress newlines.

## Error Handling

第一版不提供阈值失败策略，但不能让单个 case 静默失败。

如果 `run_research()` 对某个 case 抛出异常：

- JSON mode 中该 case 包含：
  - `query`
  - `duration_ms`
  - `error`: 固定字符串 `Research workflow failed.`
  - 其他计数字段为 `0` 或 `false`
- Markdown mode 中该 case 仍输出一行，`Critique passed` 为 `false`，并在表格后追加 `## Errors` section，列出 query 和固定错误字符串。
- 脚本整体退出码仍为 `0`，因为第一版不做 CI gate。
- 不输出 raw exception message，避免泄露 provider payload、路径或 secrets。

## 测试策略

新增 `tests/test_benchmark_research.py`。

测试全部离线，不访问公网，不调用真实 LLM。

覆盖点：

- JSON mode 输出 expected top-level keys 和 per-case metric fields。
- Markdown mode 输出标题、case 表格和 summary 表格。
- `run_research` 被调用时会看到清理后的 env；已有 opt-in env 不应泄漏到 benchmark case。
- `reference_count` 能统计当前 Reporter 生成的 numbered references。
- `run_research` 异常时输出固定错误，不包含 raw exception text，退出仍为 success。
- Markdown table cell escaping 覆盖 `|` 和换行。

测试应通过直接调用脚本中的纯函数为主，避免 subprocess。可提供 `main(argv)` 和 `build_benchmark_payload(cases, run_research_func)` 这类小函数，便于测试。

## README 更新

在 “计划脚本” 区域将 `scripts/benchmark_research.py` 从后续路线图改为当前可用，说明：

- 默认离线运行固定 benchmark cases。
- 输出 JSON 或 `--markdown` 表格。
- 不访问公网，不调用 LLM，不做阈值 gate。

## 验证

实现完成后运行：

```powershell
python -m pytest tests/test_benchmark_research.py tests/test_graph.py -q
python -m pytest -q
python -m ruff check .
```

Smoke：

```powershell
python scripts/benchmark_research.py
python scripts/benchmark_research.py --markdown
```

JSON smoke 期望包含：

```text
"cases"
"summary"
"total_llm_calls": 0
```

Markdown smoke 期望包含：

```text
# InsightGraph Benchmark
## Summary
```
