# InsightGraph Scripts

## 脚本状态

| 脚本 | 状态 | 用途 |
|------|------|------|
| `scripts/run_research.py` | 当前可用 | 运行 research workflow，默认输出 Markdown；支持 stdin `-`、`--preset offline\|live-llm` 和 `--output-json` 输出 CLI/API 对齐结构 |
| `scripts/run_with_llm_log.py` | 当前可用 | 运行 research workflow，stdout 输出 Markdown，并将安全 LLM metadata 写入 `llm_logs/`；不记录 prompt、completion、raw response 或 API key |
| `scripts/validate_sources.py` | 当前可用 | 离线校验 Markdown 报告 citation 与 References；支持文件路径或 stdin `-`，默认 JSON 输出，`--markdown` 输出表格；不联网校验 URL 可访问性 |
| `scripts/benchmark_research.py` | 当前可用 | 离线运行固定 benchmark cases，输出 JSON 或 `--markdown` 表格；不访问公网、不调用 LLM、不做阈值 gate |
| `scripts/validate_document_reader.py` | 当前可用 | 离线验证当前本地 TXT/Markdown/HTML/PDF `document_reader` 行为、长文档 bounded snippets 和 JSON query ranking，默认 JSON 输出，`--markdown` 输出表格；PDF OCR、页级分页与向量语义检索验证属于后续路线图 |
| `scripts/validate_github_search.py` | 当前可用 | 离线验证默认 deterministic `github_search` 和 fake live GitHub provider 映射，默认 JSON 输出，`--markdown` 输出表格；不读取 token、不请求 GitHub API |

## run_research.py

```bash
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_research.py - < query.txt
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
INSIGHT_GRAPH_USE_DOCUMENT_READER=1 python scripts/run_research.py '{"path":"report.md","query":"enterprise pricing"}'
```

该脚本复用当前 research workflow。默认 `--preset offline` 不应用 live defaults；当未预先设置 opt-in 工具/LLM 环境变量时，会使用 deterministic mock evidence。显式设置的 opt-in 环境变量仍会被保留并生效，与现有 CLI 语义一致；`--preset live-llm` 会使用与 CLI 相同的 live runtime defaults。

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

## validate_github_search.py

```bash
python scripts/validate_github_search.py
python scripts/validate_github_search.py --markdown
```

该脚本验证默认 offline `github_search` 以及 `INSIGHT_GRAPH_GITHUB_PROVIDER=live` 的 fake GitHub API 映射路径；不读取 `GITHUB_TOKEN`、不请求真实 GitHub API，也不调用 LLM。
