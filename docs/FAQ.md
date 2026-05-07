# 常见问题（FAQ）

## 安装与配置

### Q: 如何安装 InsightGraph？

**A**: 有两种方式：

```bash
# 开发版（包含测试工具）
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

# 生产版
pip install insightgraph
```

详细参考 [QUICK_START.md](QUICK_START.md)。

### Q: 需要 API Key 吗？

**A**: 不一定：

- **离线模式**: 无需 API Key，使用 mock 数据（用于测试）
- **实时搜索**: 需要搜索 provider key（DuckDuckGo 免费，SerpAPI 100/月免费）
- **LLM 分析**: 需要 OpenAI 兼容 endpoint key（DeepSeek、OpenAI、Azure、本地等）

设置环境变量：

```bash
export INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo
export INSIGHT_GRAPH_LLM_BASE_URL=https://api.deepseek.com/v1
export INSIGHT_GRAPH_LLM_API_KEY=sk-...
```

### Q: 如何配置 DuckDuckGo 搜索？

**A**: DuckDuckGo 默认免费无限制：

```bash
INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo \
INSIGHT_GRAPH_USE_WEB_SEARCH=1 \
  insight-graph research "Your query"
```

如需代理（国内用户）：

```bash
export INSIGHT_GRAPH_SEARCH_PROXY=http://127.0.0.1:7890
```

### Q: 如何配置 SerpAPI？

**A**: SerpAPI 提供 100/月 免费额度：

1. 注册 [SerpAPI](https://serpapi.com/)
2. 获取 API Key
3. 设置环境变量：

```bash
export INSIGHT_GRAPH_SEARCH_PROVIDER=serpapi
export INSIGHT_GRAPH_SERPAPI_KEY=your-api-key
export INSIGHT_GRAPH_USE_WEB_SEARCH=1
```

### Q: 如何配置本地 LLM？

**A**: 使用任何 OpenAI 兼容 endpoint（Ollama、LM Studio、vLLM、LlamaCPP 等）：

```bash
# 启动本地 LLM 服务（例如 Ollama）
ollama run deepseek-r1:7b

# 配置 InsightGraph
export INSIGHT_GRAPH_LLM_BASE_URL=http://localhost:11434/v1
export INSIGHT_GRAPH_LLM_MODEL=deepseek-r1:7b
export INSIGHT_GRAPH_ANALYST_PROVIDER=llm
export INSIGHT_GRAPH_REPORTER_PROVIDER=llm

# 运行研究
insight-graph research "Your query"
```

## 功能使用

### Q: 离线模式和实时模式有什么区别？

**A**:

| 特性 | 离线模式 | 实时模式 |
|-----|---------|---------|
| 网络访问 | ❌ | ✅ |
| LLM 分析 | ❌ | ✅ |
| 速度 | ⚡ 快 | 🌍 慢 |
| 真实证据 | ❌ | ✅ |
| 成本 | 免费 | 需要 API Key |
| 用途 | 测试/演示 | 生产/真实研究 |

离线模式使用预定义数据集，适合测试。实时模式需要网络和 LLM。

### Q: 如何启用多源采集？

**A**: 默认只用第一个可用的搜索工具。启用多源：

```bash
INSIGHT_GRAPH_USE_WEB_SEARCH=1 \
INSIGHT_GRAPH_USE_GITHUB_SEARCH=1 \
INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION=1 \
  insight-graph research "Find best practices"
```

支持的源：
- Web Search（DuckDuckGo / SerpAPI / Google）
- GitHub Search（REST API）
- SEC Filings（上市公司财报）
- SEC Financials（上市公司财务数据）
- News Search（新闻/产品公告）
- Document Reader（本地文档）

### Q: 如何验证 URL 和引用？

**A**: 启用 URL 验证和引用支持：

```bash
insight-graph research \
  --reporter-validate-urls \
  "Your query"

# 或环境变量
export INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=1
```

Reporter 会：
1. 验证报告中每个 URL 的可达性
2. 检查引用的证据 ID 有效性
3. 移除失效链接
4. 标记验证状态

### Q: 如何限制搜索结果数量？

**A**: 使用环境变量控制：

```bash
export INSIGHT_GRAPH_SEARCH_LIMIT=5        # 搜索结果数
export INSIGHT_GRAPH_MAX_FETCHES=20        # 最多 fetch URL 数
export INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN=100  # 最多证据数
export INSIGHT_GRAPH_MAX_TOOL_CALLS=200    # 最多工具调用数
```

### Q: 如何从本地文档进行研究？

**A**: 使用文档读取工具：

```bash
# 启用本地文档读取
INSIGHT_GRAPH_USE_DOCUMENT_READER=1 \
  insight-graph research "README.md"

# 或使用 JSON 查询
INSIGHT_GRAPH_USE_DOCUMENT_READER=1 \
  insight-graph research '{
    "path": "report.pdf",
    "query": "enterprise pricing"
  }'
```

### Q: 如何在 API 中实现长时间运行的任务？

**A**: 使用 Job API，支持异步执行和进度轮询：

```bash
# 启动研究任务
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Your query",
    "preset": "live-research"
  }'

# 返回：{"job_id": "abc123", "status": "running"}

# 查询进度
curl http://localhost:8000/research/jobs/abc123

# WebSocket 实时进度
wscat -c ws://localhost:8000/research/stream/abc123
```

详见 [API 文档](reference-parity-roadmap.md)。

## 性能优化

### Q: 如何加速研究过程？

**A**:

1. **减少搜索结果**:
   ```bash
   export INSIGHT_GRAPH_SEARCH_LIMIT=3
   export INSIGHT_GRAPH_MAX_FETCHES=10
   ```

2. **并行工具调用**:
   ```bash
   export INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION=1
   export INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS=3
   ```

3. **禁用 URL 验证**:
   ```bash
   export INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=0
   ```

4. **使用快速 LLM**:
   ```bash
   export INSIGHT_GRAPH_LLM_MODEL=gpt-4-turbo
   ```

### Q: 如何减少 token 使用量？

**A**:

1. **减少证据数量**:
   ```bash
   export INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN=50
   ```

2. **禁用冗长输出**:
   ```bash
   export INSIGHT_GRAPH_REPORTER_VERBOSE=0
   ```

3. **使用便宜的模型**:
   ```bash
   export INSIGHT_GRAPH_LLM_MODEL=gpt-3.5-turbo
   ```

4. **启用对话压缩**:
   ```bash
   export INSIGHT_GRAPH_CONVERSATION_COMPRESSION=1
   ```

### Q: 如何查看 LLM 调用日志？

**A**: 启用 LLM 日志：

```bash
python scripts/run_with_llm_log.py \
  "Your research query" \
  --output reports/llm-trace.jsonl

# 查看日志
cat reports/llm-trace.jsonl | jq .
```

## 故障排除

### Q: 出错 "ModuleNotFoundError"？

**A**: 确保安装正确且 Python 环境激活：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

# 验证
python -c "import insight_graph; print(insight_graph.__version__)"
```

### Q: 搜索无结果？

**A**: 检查搜索配置：

```bash
# 测试搜索工具
python -c "from insight_graph.tools.search_providers import web_search; print(web_search('Python'))"

# 检查网络和代理
ping google.com
echo $INSIGHT_GRAPH_SEARCH_PROXY

# 增加搜索限制
export INSIGHT_GRAPH_SEARCH_LIMIT=10
```

### Q: LLM API 调用失败？

**A**: 检查 endpoint 和 key：

```bash
# 验证 endpoint
curl -X POST $INSIGHT_GRAPH_LLM_BASE_URL/chat/completions \
  -H "Authorization: Bearer $INSIGHT_GRAPH_LLM_API_KEY"

# 查看详细错误
python -m insight_graph.cli research "Your query" -v
```

### Q: 报告生成很慢？

**A**: 检查：

1. **网络延迟**: 增加超时时间
   ```bash
   export INSIGHT_GRAPH_REQUEST_TIMEOUT=60
   ```

2. **LLM 响应慢**: 检查 API 和模型
   ```bash
   export INSIGHT_GRAPH_LLM_MODEL=gpt-4-turbo
   ```

3. **证据过多**: 减少证据数量
   ```bash
   export INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN=50
   ```

### Q: 内存占用过高？

**A**: 优化资源使用：

```bash
# 减少并发任务
export INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS=2

# 减少缓存
export INSIGHT_GRAPH_CACHE_SIZE=100

# 不持久化报告
export INSIGHT_GRAPH_REPORT_WRITEBACK=0
```

## 部署

### Q: 如何部署到生产环境？

**A**: 参考 [部署指南](deployment.md)。简要步骤：

```bash
# 1. 安装
python -m venv /opt/insightgraph/.venv
source /opt/insightgraph/.venv/bin/activate
pip install insightgraph "uvicorn[standard]"

# 2. 配置
export INSIGHT_GRAPH_API_KEY=your-shared-key
export INSIGHT_GRAPH_LLM_BASE_URL=...
export INSIGHT_GRAPH_LLM_API_KEY=...

# 3. 启动
uvicorn insight_graph.api:app --host 0.0.0.0 --port 8000

# 4. 反向代理（Nginx）
# 参考 deployment.md
```

### Q: 如何使用 PostgreSQL 存储任务？

**A**: 配置 SQLite 或 PostgreSQL 后端：

```bash
# SQLite（默认）
export INSIGHT_GRAPH_JOBS_BACKEND=sqlite
export INSIGHT_GRAPH_JOBS_DB_PATH=./jobs.db

# PostgreSQL
export INSIGHT_GRAPH_JOBS_BACKEND=postgres
export INSIGHT_GRAPH_DATABASE_URL=postgresql://user:pass@localhost/insightgraph

# 安装 PostgreSQL 驱动
pip install insightgraph[postgres]
```

## 贡献与开发

### Q: 如何本地开发？

**A**: 参考 [CONTRIBUTING.md](../CONTRIBUTING.md)：

```bash
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

# 运行测试
python -m pytest tests/ -v

# 代码检查
python -m ruff check src/

# 提交 PR
git checkout -b feat/your-feature
# ... 修改代码 ...
git commit -m "feat: ..."
git push origin feat/your-feature
```

### Q: 如何添加自定义工具？

**A**: 参考 [tools/](src/insight_graph/tools/) 目录中的现有工具，创建新工具并在 ToolRegistry 中注册。

### Q: 如何扩展 LLM provider？

**A**: 实现 `BaseLLMClient` 接口，添加到 llm/ 目录。参考现有实现了解详情。

## 更多帮助

- 📖 完整文档: [docs/](docs/)
- 🐛 报告 bug: [GitHub Issues](https://github.com/Caser-86/InsightGraph/issues)
- 💬 讨论: [GitHub Discussions](https://github.com/Caser-86/InsightGraph/discussions)
- 🤝 贡献: [CONTRIBUTING.md](../CONTRIBUTING.md)
