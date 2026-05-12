# 快速开始

这份文档帮助你在 5 到 10 分钟内跑通 InsightGraph。

## 适用场景

- 先离线体验完整研究流程
- 接入 LLM 与联网搜索生成正式长报告
- 启动 API 与 Dashboard 做本地演示

## 环境要求

- Python 3.11+
- 可选：OpenAI-compatible LLM endpoint
- 可选：DuckDuckGo / SerpAPI / Google 搜索配置

## 安装

```bash
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## 第一次运行

### 离线模式

```bash
insight-graph research "对比 Cursor、OpenCode 和 GitHub Copilot"
```

特点：

- 不访问公网
- 不调用 LLM
- 适合本地验证、CI、结构演示

### `live-research` 模式

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

## 下一步

- 中文文档索引：`docs/README.zh-CN.md`
- API 中文总览：`docs/API.zh-CN.md`
- 异步任务与记忆接口：`docs/research-jobs-api.zh-CN.md`
- 配置说明：`docs/configuration.zh-CN.md`
- 部署说明：`docs/deployment.zh-CN.md`
