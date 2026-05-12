# 快速开始

这份文档面向中文使用者，帮助你在 5-10 分钟内跑通 InsightGraph。

## 适用场景

- 想先离线体验完整研究流程
- 想接入 LLM 和联网搜索，生成更完整的正式报告
- 想启动 API 和 Dashboard 做演示

## 环境要求

- Python 3.11+
- 可选：OpenAI-compatible LLM endpoint
- 可选：DuckDuckGo、SerpAPI 或 Google Custom Search 配置

## 安装

```bash
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## 第一次运行

### 1. 离线模式

```bash
insight-graph research "对比 Cursor、OpenCode 和 GitHub Copilot"
```

特点：

- 不访问公网
- 不调用 LLM
- 适合本地验证、CI、演示基础流程

### 2. live-research 模式

```bash
insight-graph research --preset live-research "对比 Cursor、OpenCode 和 GitHub Copilot"
```

特点：

- 启用联网搜索
- 启用 LLM Analyst / Reporter
- 启用 GitHub / SEC / URL validation 等相关能力
- 可能产生 network/LLM cost

## 配置 LLM

以 DeepSeek 为例：

```bash
export INSIGHT_GRAPH_LLM_BASE_URL=https://api.deepseek.com/v1
export INSIGHT_GRAPH_LLM_API_KEY=sk-xxxxxxxx
export INSIGHT_GRAPH_ANALYST_PROVIDER=llm
export INSIGHT_GRAPH_REPORTER_PROVIDER=llm
```

也支持本地或其他 OpenAI-compatible endpoint：

```bash
export INSIGHT_GRAPH_LLM_BASE_URL=http://localhost:11434/v1
export INSIGHT_GRAPH_LLM_MODEL=your-model
export INSIGHT_GRAPH_LLM_API_KEY=dummy-or-real-key
```

## 配置搜索

### DuckDuckGo

```bash
export INSIGHT_GRAPH_USE_WEB_SEARCH=1
export INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo
```

### SerpAPI

```bash
export INSIGHT_GRAPH_USE_WEB_SEARCH=1
export INSIGHT_GRAPH_SEARCH_PROVIDER=serpapi
export INSIGHT_GRAPH_SERPAPI_KEY=your-serpapi-key
```

## 启动 API 与 Dashboard

```bash
python -m pip install "uvicorn[standard]"
uvicorn insight_graph.api:app --host 127.0.0.1 --port 8000
```

访问地址：

- Health: `http://127.0.0.1:8000/health`
- OpenAPI: `http://127.0.0.1:8000/docs`
- Dashboard: `http://127.0.0.1:8000/dashboard`

## 常用命令

```bash
insight-graph research --help
python scripts/run_research.py "Analyze Xiaomi EV strategy"
python scripts/run_with_llm_log.py "Analyze Xiaomi EV strategy"
python scripts/benchmark_research.py --markdown
```

## 下一步

- 更完整的接口说明：`docs/API.md`
- 异步任务与 Memory API：`docs/research-jobs-api.md`
- 配置项总表：`docs/configuration.md`
- 部署方式：`docs/deployment.md`
- 常见问题：`docs/FAQ.md`
