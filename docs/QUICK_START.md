# 快速开始

5 分钟内快速上手 InsightGraph。

## 需求

- Python 3.11+
- OpenAI 兼容的 LLM endpoint（或使用离线 mock 模式）

## 安装

### 方式 1: 从源代码安装（开发）

```bash
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### 方式 2: 从 PyPI 安装（生产）

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install insightgraph
```

## 配置 LLM（可选）

如果要生成中文研究报告，需要配置 LLM endpoint。

### 使用 DeepSeek

```bash
# 创建 .env 文件
cat > .env << 'EOF'
INSIGHT_GRAPH_LLM_BASE_URL=https://api.deepseek.com/v1
INSIGHT_GRAPH_LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
INSIGHT_GRAPH_ANALYST_PROVIDER=llm
INSIGHT_GRAPH_REPORTER_PROVIDER=llm
EOF
```

### 使用其他 OpenAI 兼容 API

```bash
export INSIGHT_GRAPH_LLM_BASE_URL=https://api.your-provider.com/v1
export INSIGHT_GRAPH_LLM_API_KEY=your-api-key
export INSIGHT_GRAPH_LLM_MODEL=your-model-name
export INSIGHT_GRAPH_ANALYST_PROVIDER=llm
export INSIGHT_GRAPH_REPORTER_PROVIDER=llm
```

## 运行你的第一次研究

### 1. 离线模式（无需 API Key）

```bash
insight-graph research "如何对标 Cursor 和 GitHub Copilot?"
```

输出：
```
[Planner] Planning research strategy...
[Collector] Gathering evidence from offline sources...
[Analyst] Analyzing findings...
[Reporter] Generating research report...

Report saved to: reports/research-[timestamp].md
```

### 2. 实时联网模式（需要 LLM 和搜索 API Key）

```bash
# 启用实时搜索和 LLM 分析
INSIGHT_GRAPH_USE_WEB_SEARCH=1 \
INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo \
INSIGHT_GRAPH_ANALYST_PROVIDER=llm \
INSIGHT_GRAPH_REPORTER_PROVIDER=llm \
  insight-graph research "Compare Cursor, OpenCode, and GitHub Copilot"
```

或使用预设：

```bash
insight-graph research --preset live-research "对标分析：Cursor vs OpenCode vs GitHub Copilot"
```

### 3. 使用 API 服务

启动 API 服务器：

```bash
uvicorn insight_graph.api:app --host 0.0.0.0 --port 8000
```

发送研究请求：

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "如何对标 Cursor 和 GitHub Copilot?",
    "preset": "live-research"
  }'
```

查询任务状态：

```bash
curl http://localhost:8000/health
```

## 常见选项

```bash
# 查看所有选项
insight-graph research --help

# 指定搜索引擎
insight-graph research --search-provider duckduckgo "Your query"

# 指定搜索结果数
insight-graph research --search-limit 10 "Your query"

# 指定输出目录
insight-graph research --output-dir reports/ "Your query"

# 启用 GitHub 搜索
INSIGHT_GRAPH_USE_GITHUB_SEARCH=1 \
  insight-graph research "Find open source alternatives"

# 启用 SEC 财务数据
INSIGHT_GRAPH_USE_SEC_FILINGS=1 \
  insight-graph research "Analyze Apple's financial reports"
```

## 验证安装

```bash
# 检查 CLI 命令可用
insight-graph --version

# 运行单元测试
python -m pytest tests/ -v --tb=short

# 运行离线评估
insight-graph-eval --case-file docs/evals/default.json

# 运行部署检验
insight-graph-smoke
```

## 生成的报告

报告默认保存在 `reports/` 目录，格式为 `research-[timestamp].md`。

内容包括：
- **概述 (Summary)**: 核心发现
- **深度分析 (Analysis)**: 逐点论证
- **引用 (References)**: 可验证的证据链接
- **诊断 (Diagnostics)**: 搜索/LLM 调用统计

## 下一步

- 📖 阅读 [配置文档](docs/configuration.md) 了解高级选项
- 🚀 查看 [部署指南](docs/deployment.md) 用于生产部署
- 🤝 贡献代码: 参考 [CONTRIBUTING.md](CONTRIBUTING.md)
- ❓ 问题排查: 查看 [FAQ.md](FAQ.md)

## 获取帮助

- GitHub Issues: 报告 bug 或请求功能
- 查看项目文档: [docs/](docs/)
- 检查示例脚本: [scripts/](scripts/)
