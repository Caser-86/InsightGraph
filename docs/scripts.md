# InsightGraph Scripts

## 脚本状态

| 脚本 | 状态 | 用途 |
|------|------|------|
| `scripts/run_research.py` | 当前可用 | 运行 research workflow，默认输出 Markdown；支持 stdin `-`、`--preset offline\|live-llm\|live-research` 和 `--output-json` 输出 CLI/API 对齐结构 |
| `scripts/run_with_llm_log.py` | 当前可用 | 运行 research workflow，stdout 输出 Markdown，并将安全 LLM metadata 写入 `llm_logs/`；不记录 prompt、completion、raw response 或 API key |
| `scripts/validate_sources.py` | 当前可用 | 离线校验 Markdown 报告 citation 与 References；支持文件路径或 stdin `-`，默认 JSON 输出，`--markdown` 输出表格；不联网校验 URL 可访问性 |
| `scripts/benchmark_research.py` | 当前可用 | 离线运行固定 benchmark cases，输出 JSON 或 `--markdown` 表格；不访问公网、不调用 LLM、不做阈值 gate |
| `scripts/benchmark_live_research.py` | 当前可用 | 手动 opt-in 运行 `live-research` benchmark；需要 `--allow-live` 或 `INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1`，会使用联网/LLM 配置并可能产生 network/LLM cost |
| `scripts/validate_document_reader.py` | 当前可用 | 离线验证当前本地 TXT/Markdown/HTML/PDF `document_reader` 行为、长文档 bounded snippets 和 JSON query ranking，默认 JSON 输出，`--markdown` 输出表格；PDF OCR、页级分页与向量语义检索验证属于后续路线图 |
| `scripts/validate_pdf_fetch.py` | 当前可用 | 离线验证本地 PDF reader、`search_document` PDF query/page retrieval、fake remote PDF fetch 和 PDF metadata；不访问公网 |
| `scripts/validate_github_search.py` | 当前可用 | 离线验证默认 deterministic `github_search` 和 fake live GitHub provider 映射，默认 JSON 输出，`--markdown` 输出表格；不读取 token、不请求 GitHub API |
| `insight-graph-smoke` / `scripts/smoke_deployment.py` | 当前可用 | 对已运行的 API 部署执行 smoke test：检查 `/health`、`/dashboard` 和 `/research/jobs/summary`；默认从 `INSIGHT_GRAPH_API_KEY` 读取 API key，输出 JSON |

## run_research.py

```bash
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_research.py - < query.txt
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-research --output-json
INSIGHT_GRAPH_USE_DOCUMENT_READER=1 python scripts/run_research.py '{"path":"report.md","query":"enterprise pricing"}'
```

该脚本复用当前 research workflow。默认 `--preset offline` 不应用 live defaults；当未预先设置 opt-in 工具/LLM 环境变量时，会使用 deterministic mock evidence。显式设置的 opt-in 环境变量仍会被保留并生效，与现有 CLI 语义一致；`--preset live-research` 会启用联网搜索、GitHub/SEC、多源采集、URL validation、OpenAI-compatible relevance judge、LLM Analyst 和 LLM Reporter。`--preset live-llm` 保留为轻量 web search + LLM preset。

当 `INSIGHT_GRAPH_USE_DOCUMENT_READER=1` 时，query 可以是本地文件路径，也可以是 JSON：`{"path":"report.md","query":"enterprise pricing"}`。JSON `query` 会触发 `document_reader` 的 deterministic lexical ranking，从本地文档 chunks 中优先返回词项匹配的 evidence；不使用 embeddings、LLM 或公网服务。

## run_with_llm_log.py

```bash
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_with_llm_log.py - < query.txt
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot" --log-dir tmp_llm_logs
INSIGHT_GRAPH_USE_DOCUMENT_READER=1 python scripts/run_with_llm_log.py '{"path":"report.md","query":"enterprise pricing"}' --log-dir tmp_llm_logs
```

该脚本会把本次运行的安全 LLM metadata 写入 JSON 文件。日志包含 `tool_call_log`、`llm_call_log`、summary counts 和 iterations；不包含完整报告、完整 findings、evidence pool、prompt、completion、raw response、headers、request body 或 API key。

与 `run_research.py` 一样，当 `INSIGHT_GRAPH_USE_DOCUMENT_READER=1` 时，JSON query 会触发 `document_reader` 的 deterministic lexical ranking，并同时写入安全 metadata log；不使用 embeddings、LLM retrieval 或公网服务。

## benchmark_research.py

```bash
python scripts/benchmark_research.py
python scripts/benchmark_research.py --markdown
```

该脚本会在进程内清理会改变默认工具/LLM 行为的 opt-in 环境变量，确保 benchmark 使用 offline deterministic workflow。

## benchmark_live_research.py

```bash
python scripts/benchmark_live_research.py --allow-live --output reports/live-benchmark.json
INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1 python scripts/benchmark_live_research.py --output reports/live-benchmark.json --case "Compare Cursor, OpenCode, and GitHub Copilot"
```

该脚本是手动/opt-in live benchmark，固定使用 `live-research` preset。未传 `--allow-live` 且未设置 `INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1` 时会退出，不写 artifact。启用后会访问真实网络/LLM provider，可能产生 network/LLM cost。JSON artifact 包含 URL validity count、citation precision proxy、source diversity、report depth、runtime、LLM call count 和 token totals。

## validate_sources.py

```bash
python scripts/validate_sources.py report.md
python scripts/validate_sources.py - < report.md
python scripts/validate_sources.py report.md --markdown
```

该脚本只做离线结构校验，不请求 URL，也不验证网页是否可访问。

## validate_document_reader.py

```bash
python scripts/validate_document_reader.py
python scripts/validate_document_reader.py --markdown
```

该脚本会在临时目录内创建 TXT/Markdown/HTML/PDF fixtures，并验证 `document_reader` 的成功读取、unsupported/empty/invalid 文件、缺失文件和路径越界返回空结果；不读取用户文件、不访问公网、不调用 LLM。

`document_reader` 也支持 JSON 输入按检索词选择更相关的 chunks：

```bash
INSIGHT_GRAPH_USE_DOCUMENT_READER=1 python -m insight_graph.cli research '{"path":"report.pdf","query":"enterprise pricing"}'
```

该排序是 deterministic lexical matching，不使用 embeddings、LLM 或公网服务。

## validate_pdf_fetch.py

```bash
python scripts/validate_pdf_fetch.py
python scripts/validate_pdf_fetch.py --markdown
```

该脚本会在临时目录内创建 PDF fixtures，验证 `document_reader`、`search_document`、fake remote `fetch_url` PDF extraction 和 page/chunk metadata；不访问公网、不读取用户文件、不调用 LLM。

## validate_github_search.py

```bash
python scripts/validate_github_search.py
python scripts/validate_github_search.py --markdown
```

该脚本验证默认 offline `github_search` 以及 `INSIGHT_GRAPH_GITHUB_PROVIDER=live` 的 fake GitHub API 映射路径；不读取 `GITHUB_TOKEN`、不请求真实 GitHub API，也不调用 LLM。

## insight-graph-smoke

```bash
insight-graph-smoke http://127.0.0.1:8000
INSIGHT_GRAPH_API_KEY=change-me insight-graph-smoke https://insightgraph.example.com
insight-graph-smoke https://insightgraph.example.com --timeout 10
insight-graph-smoke https://insightgraph.example.com --markdown
insight-graph-smoke https://insightgraph.example.com --output smoke.json
insight-graph-smoke https://insightgraph.example.com --markdown --output smoke.md
```

该脚本会对已运行的 API 或 reverse proxy 边界执行部署 smoke test。它检查 `/health` 可访问、`/dashboard` 返回 dashboard HTML、`/research/jobs/summary` 返回 JSON；当设置 `INSIGHT_GRAPH_API_KEY` 或传入 `--api-key` 时，会用 `Authorization: Bearer <key>` 请求受保护的 jobs summary endpoint。

退出码：全部通过为 `0`，任一 endpoint 检查失败为 `1`，CLI 参数错误或 `--output` 写入失败为 `2`。脚本默认输出 JSON；`--markdown` 输出 GitHub-flavored Markdown summary，便于粘贴到 runbook、issue 或发布记录。`--output PATH` 会把当前格式写入文件，endpoint 检查失败时仍会写出报告。报告包含 UTC `created_at`、总 `duration_ms` 和每个 endpoint check 的 `duration_ms`；Markdown 表格也会显示失败 check 的安全 error 文本。两种格式都不打印 API key、请求 body 或响应 body。

`scripts/smoke_deployment.py` remains as a repository-local compatibility wrapper around
the packaged `insight-graph-smoke` command.
