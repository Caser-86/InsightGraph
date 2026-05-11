# InsightGraph API Reference

InsightGraph 提供 REST API 用于远程研究任务管理和实时进度监控。所有端点支持 JSON 请求/响应。

> Note
> `docs/research-jobs-api.md` is the canonical reference for current async job lifecycle, cancel/retry semantics, restart/resume behavior, and memory endpoints. If examples in this file differ, prefer `docs/research-jobs-api.md`.

## OpenAPI / Swagger

实时 API 文档可在运行时访问：

```bash
# 启动 API
uvicorn insight_graph.api:app --host 127.0.0.1 --port 8000

# 访问 Swagger UI
http://127.0.0.1:8000/docs

# 访问 ReDoc 文档
http://127.0.0.1:8000/redoc

# 获取原始 OpenAPI 规范
curl http://127.0.0.1:8000/openapi.json | jq .
```

## 认证

所有非 `/health` 端点需要认证（如果配置了 `INSIGHT_GRAPH_API_KEY`）。

### 使用 Bearer Token（推荐）

```bash
curl -X POST http://localhost:8000/research \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### 使用 X-API-Key Header

```bash
curl -X POST http://localhost:8000/research \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### 在 Python 中

```python
import requests

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

response = requests.post(
    "http://localhost:8000/research",
    headers=headers,
    json={"query": "Your research query"}
)
```

### 在 JavaScript 中

```javascript
const apiKey = process.env.INSIGHT_GRAPH_API_KEY;

const response = await fetch("http://localhost:8000/research", {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${apiKey}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({ query: "Your research query" })
});

const data = await response.json();
```

## 端点

### 1. Health Check

**GET** `/health`

检查 API 是否运行。不需要认证。

**Response (200 OK)**:
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### 2. Synchronous Research

**POST** `/research`

执行同步研究（阻塞直到完成）。适合短查询和测试。

**Request**:
```json
{
  "query": "Compare Cursor and GitHub Copilot",
  "preset": "offline",
  "search_limit": 5,
  "max_fetches": 10,
  "timeout_seconds": 60
}
```

**Parameters**:
| 字段 | 类型 | 必需 | 默认 | 说明 |
|-----|------|------|------|------|
| `query` | string | ✅ | - | 研究查询 |
| `preset` | string | ❌ | `offline` | `offline`, `live-research`, `live-llm` |
| `search_limit` | int | ❌ | 3 | 搜索结果数 |
| `max_fetches` | int | ❌ | 20 | URL fetch 数量上限 |
| `max_evidence` | int | ❌ | 100 | 证据数上限 |
| `timeout_seconds` | int | ❌ | 300 | 超时时间 |
| `validate_urls` | bool | ❌ | false | 是否验证最终 URL |

**Response (200 OK)**:
```json
{
  "query": "Compare Cursor and GitHub Copilot",
  "status": "completed",
  "report": "## 对标分析\n\n...",
  "duration_ms": 5234,
  "evidence_count": 12,
  "diagnostics": {
    "search_calls": 2,
    "llm_calls": 0,
    "tool_calls": 3
  }
}
```

**Response (408 Timeout)**:
```json
{
  "error": "Research timeout exceeded 60 seconds"
}
```

### 3. Asynchronous Job

**POST** `/research/jobs`

创建异步研究任务。返回 `job_id` 用于轮询或流式监听。

**Request**:
```json
{
  "query": "Analyze recent AI coding agent trends",
  "preset": "live-research",
  "search_provider": "duckduckgo",
  "metadata": {
    "user_id": "user123",
    "project": "market-analysis"
  }
}
```

**Parameters**:
| 字段 | 类型 | 必需 | 说明 |
|-----|------|------|------|
| `query` | string | ✅ | 研究查询 |
| `preset` | string | ❌ | 预设配置 |
| `search_provider` | string | ❌ | `mock`, `duckduckgo`, `serpapi` |
| `metadata` | object | ❌ | 自定义元数据（返回在响应中） |

**Response (202 Accepted)**:
```json
{
  "job_id": "research-abc123def456",
  "status": "queued",
  "created_at": "2026-05-07T12:34:56Z",
  "query": "Analyze recent AI coding agent trends",
  "preset": "live-research"
}
```

### 4. Job Status

**GET** `/research/jobs/{job_id}`

获取任务状态和进度。

**Response (200 OK - Running)**:
```json
{
  "job_id": "research-abc123def456",
  "status": "running",
  "created_at": "2026-05-07T12:34:56Z",
  "started_at": "2026-05-07T12:34:58Z",
  "current_stage": "analyst",
  "progress": {
    "evidence_collected": 8,
    "max_evidence": 100,
    "search_calls": 2,
    "llm_calls": 1
  },
  "metadata": {
    "user_id": "user123"
  }
}
```

**Response (200 OK - Completed)**:
```json
{
  "job_id": "research-abc123def456",
  "status": "completed",
  "created_at": "2026-05-07T12:34:56Z",
  "started_at": "2026-05-07T12:34:58Z",
  "finished_at": "2026-05-07T12:40:23Z",
  "duration_seconds": 345,
  "query": "Analyze recent AI coding agent trends",
  "report": "## AI 编码助手趋势分析\n\n...",
  "result": {
    "evidence_count": 15,
    "sections": ["Overview", "Trends", "Market Analysis"],
    "diagnostics": {
      "search_calls": 3,
      "llm_calls": 2,
      "fetch_success_rate": 0.93
    }
  },
  "metadata": {
    "user_id": "user123"
  }
}
```

**Response (200 OK - Failed)**:
```json
{
  "job_id": "research-abc123def456",
  "status": "failed",
  "created_at": "2026-05-07T12:34:56Z",
  "started_at": "2026-05-07T12:34:58Z",
  "finished_at": "2026-05-07T12:35:10Z",
  "error": "LLM API key not configured",
  "error_code": "LLM_AUTH_ERROR"
}
```

**Status Values**:
| 值 | 说明 |
|----|------|
| `queued` | 等待执行 |
| `running` | 正在执行 |
| `completed` | 成功完成 |
| `failed` | 执行失败 |
| `cancelled` | 被取消 |

### 5. Job Summary

**GET** `/research/jobs/summary`

获取所有任务的统计摘要。

**Response (200 OK)**:
```json
{
  "total_jobs": 42,
  "by_status": {
    "completed": 35,
    "running": 2,
    "queued": 3,
    "failed": 2
  },
  "success_rate": 0.944,
  "average_duration_seconds": 287,
  "recent_jobs": [
    {
      "job_id": "research-xyz789",
      "status": "completed",
      "query": "...",
      "created_at": "2026-05-07T12:30:00Z"
    }
  ]
}
```

### 6. Stream Job Progress

**WebSocket** `/research/jobs/{job_id}/stream`

实时流式监听任务进度和日志。仅当 WebSocket 连接活跃时发送事件。

**JavaScript 客户端**:
```javascript
const jobId = "research-abc123";
const apiKey = process.env.INSIGHT_GRAPH_API_KEY;

const ws = new WebSocket(
  `ws://localhost:8000/research/jobs/${jobId}/stream?api_key=${apiKey}`
);

ws.onopen = () => {
  console.log("Connected to job stream");
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`[${data.stage}] ${data.message}`);
  
  if (data.stage === "reporter") {
    console.log(`Progress: ${data.progress.evidence_collected}/${data.progress.max_evidence}`);
  }
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};

ws.onclose = () => {
  console.log("Stream closed");
};
```

**Stream Events**:
```json
{
  "stage": "collector",
  "message": "Searching for evidence...",
  "timestamp": "2026-05-07T12:35:00Z",
  "progress": {
    "evidence_collected": 5,
    "max_evidence": 100,
    "search_calls": 1
  }
}
```

### 7. Cancel Job

**DELETE** `/research/jobs/{job_id}`

取消正在执行的任务。

**Response (200 OK)**:
```json
{
  "job_id": "research-abc123def456",
  "status": "cancelled",
  "message": "Job cancelled successfully"
}
```

### 8. Dashboard

**GET** `/dashboard`

访问 Web UI dashboard（零构建）。

打开浏览器：`http://localhost:8000/dashboard`

- API Key 登录
- 创建新研究
- 实时进度监控
- 报告查看和下载

## 错误处理

所有错误响应遵循统一格式：

```json
{
  "error": "Descriptive error message",
  "error_code": "ERROR_CODE",
  "details": {
    "field": "Additional context"
  }
}
```

### 常见错误

| 状态码 | 错误代码 | 说明 |
|--------|---------|------|
| 400 | INVALID_INPUT | 请求参数无效 |
| 401 | UNAUTHORIZED | API Key 缺失或无效 |
| 403 | FORBIDDEN | 权限不足 |
| 404 | NOT_FOUND | 任务不存在 |
| 408 | TIMEOUT | 研究超时 |
| 429 | RATE_LIMITED | 请求限流 |
| 500 | INTERNAL_ERROR | 服务器错误 |
| 503 | SERVICE_UNAVAILABLE | 服务暂时不可用 |

### 重试策略

对于可重试错误（429、503、5xx），使用指数退避：

```python
import time
import requests

def research_with_retry(query, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "http://localhost:8000/research",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"query": query},
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            print(f"Timeout, retrying in {wait_time}s...")
            time.sleep(wait_time)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (429, 503):
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt
                print(f"Rate limited, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
```

## 速率限制

默认限制（通过反向代理或网关配置）：

| 端点 | 限制 | 说明 |
|-----|------|------|
| `/research` | 30 req/min | 同步研究 |
| `/research/jobs` | 30 req/min | 创建异步任务 |
| `/health` | 无 | 健康检查 |

超限返回 429 Conflict with Retry-After header：

```
HTTP/1.1 429 Too Many Requests
Retry-After: 60

{
  "error": "Rate limit exceeded",
  "error_code": "RATE_LIMITED",
  "retry_after_seconds": 60
}
```

## 请求示例

### Python

```python
import requests

api_key = "your-api-key"
base_url = "http://localhost:8000"

# 同步研究
response = requests.post(
    f"{base_url}/research",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "query": "Compare Cursor and GitHub Copilot",
        "preset": "offline"
    },
    timeout=60
)
result = response.json()
print(result["report"])

# 异步任务
job_response = requests.post(
    f"{base_url}/research/jobs",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "query": "Analyze AI coding agents",
        "preset": "live-research"
    }
)
job = job_response.json()
job_id = job["job_id"]

# 轮询状态
import time
while True:
    status = requests.get(
        f"{base_url}/research/jobs/{job_id}",
        headers={"Authorization": f"Bearer {api_key}"}
    ).json()
    
    if status["status"] in ["completed", "failed"]:
        print(f"Status: {status['status']}")
        if status["status"] == "completed":
            print(status["report"])
        break
    
    print(f"Progress: {status['current_stage']}")
    time.sleep(2)
```

### cURL

```bash
# 同步研究
curl -X POST http://localhost:8000/research \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Your query",
    "preset": "offline"
  }'

# 创建异步任务
curl -X POST http://localhost:8000/research/jobs \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Your query",
    "preset": "live-research"
  }' | jq -r .job_id > job_id.txt

# 轮询状态
JOB_ID=$(cat job_id.txt)
curl http://localhost:8000/research/jobs/$JOB_ID \
  -H "Authorization: Bearer $API_KEY" | jq .

# 流式监听
wscat -c "ws://localhost:8000/research/jobs/$JOB_ID/stream?api_key=$API_KEY"
```

### JavaScript / Node.js

```javascript
const axios = require('axios');

const apiKey = process.env.INSIGHT_GRAPH_API_KEY;
const baseUrl = "http://localhost:8000";

// 异步研究，带轮询
async function researchWithPolling(query) {
  // 创建任务
  const jobResponse = await axios.post(
    `${baseUrl}/research/jobs`,
    { query, preset: "offline" },
    { headers: { Authorization: `Bearer ${apiKey}` } }
  );
  
  const jobId = jobResponse.data.job_id;
  console.log(`Created job: ${jobId}`);
  
  // 轮询直到完成
  let status = "running";
  while (status === "running" || status === "queued") {
    const statusResponse = await axios.get(
      `${baseUrl}/research/jobs/${jobId}`,
      { headers: { Authorization: `Bearer ${apiKey}` } }
    );
    
    status = statusResponse.data.status;
    console.log(`Status: ${status}`);
    
    if (status === "running") {
      await new Promise(r => setTimeout(r, 1000)); // 等待 1s
    }
  }
  
  // 返回结果
  const result = await axios.get(
    `${baseUrl}/research/jobs/${jobId}`,
    { headers: { Authorization: `Bearer ${apiKey}` } }
  );
  
  return result.data;
}

// 使用
researchWithPolling("Your query").then(result => {
  console.log(result.report);
});
```

## 最佳实践

1. **使用异步任务处理长查询** - 同步端点有 timeout，大型研究应使用 `/research/jobs`
2. **实现重试逻辑** - 网络不稳定时很有用
3. **定期检查 `/health`** - 在生产环境中用于可用性监控
4. **流式监听性能关键路径** - 使用 WebSocket 获得最低延迟的进度更新
5. **保护 API Key** - 不要在日志、URL 或版本控制中暴露
6. **监控速率限制** - 设计客户端以遵守 429 响应
7. **缓存报告** - 相同查询可能返回相同结果，考虑客户端缓存

## 故障排查

### "API Key 无效"

```bash
# 检查 API Key 是否设置
echo $INSIGHT_GRAPH_API_KEY

# 检查服务是否需要 auth
curl http://localhost:8000/health  # 应该总是成功
```

### "Connection refused"

```bash
# 检查服务是否运行
curl http://localhost:8000/health

# 检查防火墙
netstat -tlnp | grep 8000
```

### "WebSocket error"

代理可能不支持 WebSocket。使用 REST 轮询作为备选：

```python
import time

job_id = "..."
while True:
    status = requests.get(f"http://localhost:8000/research/jobs/{job_id}").json()
    if status["status"] != "running":
        break
    time.sleep(2)
```

## 版本控制

当前 API 版本: **v1**（隐含在路由中）

未来版本化计划：
- `/api/v2/research` 用于潜在的向后不兼容变更
- 当前版本无 `/api/v1/` 前缀时保持向后兼容
