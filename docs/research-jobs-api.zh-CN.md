# 异步任务与 Memory API

这是 InsightGraph 异步任务生命周期、取消/重试、重启恢复、报告导出和 Memory API 的中文权威说明。

## 任务接口

- `POST /research/jobs`
- `GET /research/jobs`
- `GET /research/jobs/summary`
- `GET /research/jobs/{job_id}`
- `POST /research/jobs/{job_id}/cancel`
- `POST /research/jobs/{job_id}/retry`
- `DELETE /research/jobs/{job_id}`
- `GET /research/jobs/{job_id}/report.md`
- `GET /research/jobs/{job_id}/report.html`
- `WS /research/jobs/{job_id}/stream`

## Memory 接口

- `GET /memory`
- `POST /memory/search`
- `DELETE /memory/{memory_id}`

## 取消语义

- `queued` 可取消
- `running` 也可取消
- 终态任务再次取消返回 `409`

错误文案：

```json
{"detail":"Only queued or running research jobs can be cancelled."}
```

## 重试语义

只有 `failed` 和 `cancelled` 可重试。重试会创建一个新的 queued job，原任务不变。

## 保留与清理

- terminal job retention 仅作用于 `succeeded` / `failed` / `cancelled`
- queued / running 不会被 cleanup 删除
- `INSIGHT_GRAPH_RESEARCH_JOBS_TERMINAL_RETENTION_DAYS` 控制按时间清理
- SQLite cleanup 删除匹配终态任务行
- artifact retention 是外部概念，不随任务清理自动删除

## 重启恢复

启用方式：

```bash
export INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite
export INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/path/jobs.sqlite3
export INSIGHT_GRAPH_RESEARCH_JOBS_STARTUP_WORKER=1
export INSIGHT_GRAPH_CHECKPOINT_RESUME=1
```

行为：

- queued jobs 会在启动后继续被 worker claim
- expired running jobs 会重新进入可 claim 状态
- checkpoint resume 可从最近 GraphState 继续

## Memory 写回

开启：

```bash
export INSIGHT_GRAPH_MEMORY_WRITEBACK=1
```

成功报告会写回：

- summary
- entities
- supported claims
- reference metadata
- source reliability notes
