# InsightGraph 架构说明

InsightGraph 当前唯一正式 live 产品路径是 `live-research`。离线路径继续作为 deterministic 测试与 CI fallback。

## 核心链路

```text
CLI / API / Dashboard
  -> LangGraph StateGraph
  -> Planner -> Collector/Executor -> Analyst -> Critic -> Reporter
  -> Search / fetch / GitHub / SEC / local document tools
  -> Evidence scoring / citation support / report quality review
  -> Markdown report / JSON diagnostics / optional memory writeback
```

## 主要模块

- `agents/`：任务拆解、采集、分析、评审、报告生成
- `tools/`：搜索、抓取、GitHub、SEC、本地文档和文件工具
- `report_quality/`：研究计划、证据评分、引用支持、质量评审
- `llm/`：OpenAI-compatible 客户端、trace、router
- `memory/`：长期记忆、embedding、report writeback
- `persistence/`：checkpoint store 与 migrations
- `research_jobs*.py`：异步任务生命周期、SQLite lease、恢复路径

## 设计原则

- 证据优先，不用自由发挥替代引用
- live 能力显式 opt-in
- 高风险运行面默认 deferred
- 先保证报告质量，再扩展更高风险能力
