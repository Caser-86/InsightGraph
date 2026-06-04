# InsightGraph API 总览

这份文档是 API 的中文入口说明，帮助你快速理解项目公开接口面。

异步任务、取消/重试、重启恢复和 Memory API 的权威说明以：

- `docs/research-jobs-api.zh-CN.md`

为准。

## 主要接口

### 公开接口

- `GET /health`
- `GET /dashboard`
- `GET /docs`
- `GET /redoc`
- `GET /openapi.json`

### 配置 `INSIGHT_GRAPH_API_KEY` 后受保护的接口

- `POST /research`
- `GET /memory`
- `POST /memory/search`
- `DELETE /memory/{memory_id}`
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

## 鉴权方式

可使用任一方式：

- `Authorization: Bearer <key>`
- `X-API-Key: <key>`

示例：

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H "Authorization: Bearer $INSIGHT_GRAPH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor and GitHub Copilot"}'
```

## 同步研究接口

`POST /research` 适合：

- 小查询
- 开发调试
- 快速拿到最终结果

常见请求字段：

- `query`
- `preset`
- `report_intensity`
- `single_entity_detail_mode`
- `relevance_judge`
- `fetch_rendered`
- `search_provider`
- `web_search_mode`

常见返回字段：

- `report_markdown`
- `findings`
- `competitive_matrix`
- `tool_call_log`
- `llm_call_log`
- `evidence_pool`
- `quality`
- `quality_cards`
- `runtime_diagnostics`

## Memory API

### 列表

```bash
curl http://127.0.0.1:8000/memory
```

### 搜索

```bash
curl -X POST http://127.0.0.1:8000/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Xiaomi EV supply chain", "limit": 5}'
```

### 删除

```bash
curl -X DELETE http://127.0.0.1:8000/memory/memory-123
```

## Dashboard

访问：

```text
http://127.0.0.1:8000/dashboard
```

适合做：

- 提交任务
- 观察执行状态
- 查看证据与 citation support
- 查看报告质量卡片
- 下载 Markdown / HTML 报告
