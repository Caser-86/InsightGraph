# InsightGraph 部署说明

适用于私有演示、内部工具、运维可控环境。

## 推荐形态

- Python 3.11+
- `uvicorn` 运行 `insight_graph.api:app`
- SQLite 持久化 jobs
- 可选 PostgreSQL checkpoints
- 可选 pgvector memory
- 反向代理 / VPN / API gateway 前置

## 启动

```bash
uvicorn insight_graph.api:app --host 127.0.0.1 --port 8000
```

## API 鉴权

```bash
export INSIGHT_GRAPH_API_KEY="replace-with-shared-demo-key"
```

## 存储矩阵

- jobs：`memory` / `sqlite`
- checkpoint：`memory` / `postgres`
- memory：`memory` / `pgvector`
- document retrieval：local JSON / optional pgvector

## 重启恢复

```bash
export INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite
export INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/data/jobs.sqlite3
export INSIGHT_GRAPH_RESEARCH_JOBS_STARTUP_WORKER=1
export INSIGHT_GRAPH_CHECKPOINT_RESUME=1
```

效果：

- queued jobs 可在启动时被 claim
- expired running jobs 会重新入队
- checkpoint resume 可从最近状态继续

## 部署 smoke

```bash
insight-graph-smoke http://127.0.0.1:8000
```
