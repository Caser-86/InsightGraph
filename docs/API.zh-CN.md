# InsightGraph API 总览

这份文档是中文 API 入口说明。异步任务、取消/重试、重启恢复、Memory API 的权威说明请优先看：

- `docs/research-jobs-api.zh-CN.md`

## 主要端点

### 公共端点

- `GET /health`
- `GET /dashboard`
- `GET /docs`
- `GET /redoc`
- `GET /openapi.json`

### 设置 `INSIGHT_GRAPH_API_KEY` 后受保护的端点

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

- `Authorization: Bearer <key>`
- `X-API-Key: <key>`

## 同步研究接口

`POST /research` 适合单次快速执行，直接返回最终报告 payload。

常用请求字段：

- `query`
- `preset`
- `report_intensity`
- `single_entity_detail_mode`
- `relevance_judge`
- `fetch_rendered`
- `search_provider`
- `web_search_mode`

常见响应字段：

- `report_markdown`
- `findings`
- `competitive_matrix`
- `evidence_pool`
- `tool_call_log`
- `llm_call_log`
- `quality`
- `quality_cards`
- `runtime_diagnostics`
