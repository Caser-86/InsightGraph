# InsightGraph Configuration

InsightGraph defaults to deterministic/offline behavior. Live search, live LLM, GitHub API access, and local file/document tools require explicit opt-in environment variables.

Use `--preset live-research` for a reference-style networked research run. It sets `INSIGHT_GRAPH_USE_WEB_SEARCH=1`, `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo`, `INSIGHT_GRAPH_SEARCH_LIMIT=5`, `INSIGHT_GRAPH_USE_GITHUB_SEARCH=1`, `INSIGHT_GRAPH_GITHUB_PROVIDER=live`, `INSIGHT_GRAPH_USE_SEC_FILINGS=1`, `INSIGHT_GRAPH_USE_SEC_FINANCIALS=1`, `INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION=1`, `INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS=3`, `INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=1`, `INSIGHT_GRAPH_RELEVANCE_FILTER=1`, and `INSIGHT_GRAPH_RELEVANCE_JUDGE=deterministic` without enabling LLM Analyst or Reporter. Fetched responses are size-bounded and oversized `Content-Length` responses are rejected before body reads; long HTML pages are split into bounded evidence chunks with `chunk_index` and `section_heading` metadata; fetched PDF responses emit docs evidence with `chunk_index` and `document_page` metadata. JavaScript-rendered fetch is optional via `INSIGHT_GRAPH_FETCH_RENDERED=1` and requires Playwright to be installed separately. Use `--preset live-llm` or explicit LLM environment variables when model-generated analysis/reporting is desired.

## Search Provider 配置

`web_search` 默认使用 deterministic mock provider，测试和默认 CLI 不访问公网。搜索结果会通过 bounded pre-fetch pipeline 转为 verified evidence：fetch attempts 同时受 search limit 和 `INSIGHT_GRAPH_MAX_FETCHES` 约束，单个 URL fetch 失败不会中断其他结果，原始 query 会传给 `fetch_url` 用于长 HTML/PDF chunk ranking。需要在工具层使用真实搜索时，可显式启用 DuckDuckGo 后直接调用 `web_search` 或通过 `ToolRegistry` 运行该工具：

```bash
INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo INSIGHT_GRAPH_SEARCH_LIMIT=3 python -c "from insight_graph.tools.web_search import web_search; print(web_search('Compare Cursor, OpenCode, and GitHub Copilot'))"
```

当前 CLI 的 Planner 默认仍选择 `mock_search`，不会因为设置 DuckDuckGo provider 而自动联网。需要让研究流调用 `web_search` 时，显式设置 `INSIGHT_GRAPH_USE_WEB_SEARCH=1`；此时 `INSIGHT_GRAPH_SEARCH_PROVIDER` 再决定 `web_search` 使用 mock provider 还是 DuckDuckGo provider。

需要采集 GitHub 风格证据时，可设置 `INSIGHT_GRAPH_USE_GITHUB_SEARCH=1`。`github_search` 默认使用 deterministic/offline provider，返回稳定 verified GitHub evidence，不调用 GitHub API、不需要 token，也不受 rate limit 影响。需要真实 GitHub repository search 时，可额外设置 `INSIGHT_GRAPH_GITHUB_PROVIDER=live`；此时会调用 GitHub REST Search API。`INSIGHT_GRAPH_GITHUB_TOKEN` 或 `GITHUB_TOKEN` 可选，有 token 时用于提高 rate limit，无 token 时使用匿名请求。live provider 出现网络、鉴权、rate limit 或响应解析错误时返回空 evidence，不中断 workflow。

```bash
INSIGHT_GRAPH_USE_GITHUB_SEARCH=1 INSIGHT_GRAPH_GITHUB_PROVIDER=live INSIGHT_GRAPH_GITHUB_LIMIT=3 python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

需要只采集新闻和产品公告风格证据而不访问公网时，可设置 `INSIGHT_GRAPH_USE_NEWS_SEARCH=1`。第一版 `news_search` 是 deterministic/offline 工具，返回稳定 verified news evidence，不调用新闻 API、不需要 token，也不受 rate limit 影响。若同时启用 `INSIGHT_GRAPH_USE_WEB_SEARCH` 或 `INSIGHT_GRAPH_USE_GITHUB_SEARCH`，Planner 会按 web search、GitHub search、news search、mock search 的顺序选择第一个启用工具。

需要从本地 TXT/Markdown/HTML/PDF 文档生成 evidence 时，可设置 `INSIGHT_GRAPH_USE_DOCUMENT_READER=1` 并把用户请求写成本地文件路径，例如 `README.md`。当前 `document_reader` 读取当前工作目录内的 `.txt`、`.md`, `.markdown`, `.html`, `.htm`, `.pdf` 文件；长文档会返回最多 5 条 500 字符 snippets，并在相邻 snippets 间保留 100 字符重叠；也可用 JSON 输入提供检索词，例如 `{"path":"report.pdf","query":"enterprise pricing"}`，此时会用 deterministic lexical matching 排序 chunks，不调用 embedding 或 LLM。文档 evidence 会记录可选的 `chunk_index`、`document_page` 和 `section_heading` 元数据，用于后续 TOC/page-aware retrieval。不读取工作目录外路径、不读取 URL，也不做 PDF OCR 或向量语义检索。若同时启用搜索工具，Planner 会按 web search、GitHub search、news search、document reader、mock search 的顺序选择第一个启用工具。

需要安全浏览本地项目素材时，可使用只读文件工具：`INSIGHT_GRAPH_USE_READ_FILE=1` 将用户请求作为 cwd 内安全文本文件路径读取，当前支持 `.txt`、`.md`、`.markdown`、`.py`、`.json`、`.toml`、`.yaml`、`.yml` 且单文件不超过 64 KiB；`INSIGHT_GRAPH_USE_LIST_DIRECTORY=1` 将用户请求作为 cwd 内目录路径列出一层内容。第一版只读文件工具不会写文件、不会递归扫描、不会读取工作目录外路径，也不会执行代码。`INSIGHT_GRAPH_USE_WRITE_FILE=1` 将用户请求作为 JSON 写入请求处理，格式为 `{"path":"notes.md","content":"Notes."}`。第一版 `write_file` 只会在 cwd 内创建新的安全文本文件，不覆盖已有文件、不自动创建父目录、不执行代码；若同时启用 read/list 工具，Planner 优先选择只读工具。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_USE_WEB_SEARCH` | `1` / `true` / `yes` 时 Planner collect subtask 使用 `web_search` | 未启用 |
| `INSIGHT_GRAPH_USE_GITHUB_SEARCH` | `1` / `true` / `yes` 时 Planner collect subtask 使用 `github_search`；若同时启用 web search，则 web search 优先 | 未启用 |
| `INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION` | `1` / `true` / `yes` 时 Planner collect subtask 可同时使用 web、GitHub、news 等多个采集工具 | 未启用 |
| `INSIGHT_GRAPH_USE_SEC_FILINGS` | `1` / `true` / `yes` 时 Planner 可为已知上市公司 ticker/name 使用 SEC EDGAR filings evidence | 未启用 |
| `INSIGHT_GRAPH_USE_SEC_FINANCIALS` | `1` / `true` / `yes` 时 Planner 可为已知上市公司 ticker/name 使用 SEC companyfacts revenue/net income/assets evidence | 未启用 |
| `INSIGHT_GRAPH_USE_NEWS_SEARCH` | `1` / `true` / `yes` 时 Planner collect subtask 使用 deterministic `news_search`；若同时启用 web 或 GitHub search，则前者优先 | 未启用 |
| `INSIGHT_GRAPH_USE_DOCUMENT_READER` | `1` / `true` / `yes` 时 Planner collect subtask 使用本地 `document_reader`；若同时启用搜索工具，则搜索工具优先 | 未启用 |
| `INSIGHT_GRAPH_USE_READ_FILE` | `1` / `true` / `yes` 时 Planner collect subtask 使用本地只读 `read_file`；搜索工具和 `document_reader` 优先 | 未启用 |
| `INSIGHT_GRAPH_USE_LIST_DIRECTORY` | `1` / `true` / `yes` 时 Planner collect subtask 使用本地只读 `list_directory`；搜索工具、`document_reader` 和 `read_file` 优先 | 未启用 |
| `INSIGHT_GRAPH_USE_WRITE_FILE` | `1` / `true` / `yes` 时 Planner collect subtask 使用 create-only `write_file`；搜索工具、`document_reader`、`read_file` 和 `list_directory` 优先 | 未启用 |
| `INSIGHT_GRAPH_SEARCH_PROVIDER` | `mock` 或 `duckduckgo` | `mock` |
| `INSIGHT_GRAPH_SEARCH_LIMIT` | `web_search` 候选 URL pre-fetch 数量 | `3` |
| `INSIGHT_GRAPH_FETCH_RENDERED` | `1` / `true` / `yes` 时 `fetch_url` 优先尝试 optional Playwright rendered fetch，失败时回退到 bounded HTTP fetch | 未启用 |
| `INSIGHT_GRAPH_GITHUB_PROVIDER` | `github_search` provider，支持默认离线 `mock` 或 opt-in GitHub API `live` | `mock` |
| `INSIGHT_GRAPH_GITHUB_LIMIT` | live GitHub repository search 返回数量，范围 `1` 到 `10` | `3` |
| `INSIGHT_GRAPH_GITHUB_TOKEN` | 可选 GitHub API token；未设置时回退到 `GITHUB_TOKEN`，仍可匿名请求 | - |
| `INSIGHT_GRAPH_DOCUMENT_RETRIEVAL` | `document_reader` long-document retrieval mode，支持默认 lexical `deterministic` 或 opt-in deterministic embedding `vector` ranking | `deterministic` |

## Domain Profiles

Code-backed domain profiles are extended by Markdown files under `src/insight_graph/report_quality/domains/*.md`. Each file uses simple frontmatter for IDs/source policy and Markdown lists for report sections, required questions, and detection keywords. The default test/runtime path remains offline and deterministic.

Built-in Markdown profile example: `biotech_finance`, used for biotech/clinical/FDA/pipeline finance-style reports.

## Research Budgets

全局 research budgets 用于约束长跑采集任务。无效、空值或小于等于 0 的值会回退到默认值。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_MAX_TOOL_CALLS` | 单次研究最多执行的 tool call 数 | `20` |
| `INSIGHT_GRAPH_MAX_STEPS` | 预留的 workflow step budget，供后续 agent loop/checkpoint 使用 | `10` |
| `INSIGHT_GRAPH_MAX_FETCHES` | 预留的 fetch budget，供后续 fetch/pre-fetch 集中管控使用 | `10` |
| `INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN` | 单次研究最终保留的 evidence 数上限 | `20` |
| `INSIGHT_GRAPH_MAX_TOKENS` | 单次研究已记录 LLM total token 上限；耗尽后 Analyst/Reporter 回退 deterministic，OpenAI relevance judge 保守拒绝新 LLM 判断 | `50000` |
| `INSIGHT_GRAPH_MAX_TOOL_ROUNDS` | Executor 对每个 planned tool/subtask collection loop 允许的最大轮数；未设置时沿用 `INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS` | `INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS` |
| `INSIGHT_GRAPH_CONVERSATION_COMPRESSION` | `1` / `true` / `yes` 时 Executor 在 collection loop 后写入 deterministic `GraphState.conversation_summary` | 未启用 |

## Research Jobs Persistence

`INSIGHT_GRAPH_RESEARCH_JOBS_PATH` enables an opt-in JSON store for API research job metadata. When unset, jobs remain process-local memory only unless SQLite storage is explicitly selected. When set, the API loads job metadata from the configured JSON file at startup and writes job state changes back to that file with atomic replace semantics.

For multi-process-safe job metadata storage, set `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite` and `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/path/jobs.sqlite3`. With SQLite selected, `INSIGHT_GRAPH_RESEARCH_JOBS_PATH` is only an optional startup import source. SQLite worker lease metadata is internal and does not change public API responses.

For JSON metadata persistence, queued or running jobs from a previous process are restored as failed with `Research job did not complete before server restart.` SQLite storage keeps queued jobs in the queue and requeues expired running jobs through worker lease claim. The API does not automatically resume interrupted workflow execution or rerun unfinished jobs without a later worker claim/retry.

## Checkpoint Persistence

Checkpoint persistence is opt-in and separate from research job metadata. The default backend is in-memory and does not require services. PostgreSQL checkpoints require installing the optional dependency group, for example `pip install '.[postgres]'`.

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_CHECKPOINT_BACKEND` | `memory` 或 opt-in `postgres` | `memory` |
| `INSIGHT_GRAPH_POSTGRES_DSN` | PostgreSQL DSN used when checkpoint backend is `postgres` | - |
| `INSIGHT_GRAPH_CHECKPOINT_RESUME` | `1` / `true` / `yes` 时 API/background research jobs pass `job_id` as checkpoint `run_id` and resume from existing checkpoints | 未启用 |

`PostgresCheckpointStore` persists one latest `GraphState` payload per `run_id` in `insight_graph_checkpoints`. `run_research_with_events(..., run_id=..., checkpoint_store=..., resume=True)` can load an existing checkpoint and continue from the next event-runner stage. When `INSIGHT_GRAPH_CHECKPOINT_RESUME=1`, API/background research jobs use the job ID as the checkpoint run ID.

## Long-Term Memory

Research memory is opt-in. The default backend is in-memory and is useful only for process-local tests. The pgvector backend uses the same PostgreSQL DSN and requires the database `vector` extension.

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_MEMORY_BACKEND` | `memory` 或 opt-in `pgvector` | `memory` |
| `INSIGHT_GRAPH_POSTGRES_DSN` | PostgreSQL DSN used when memory backend is `pgvector` | - |
| `INSIGHT_GRAPH_EMBEDDING_PROVIDER` | Research memory embedding provider；目前支持 `deterministic` | `deterministic` |
| `INSIGHT_GRAPH_USE_MEMORY_CONTEXT` | `1` / `true` / `yes` 时 Planner 检索 long-term memory 并写入 `GraphState.memory_context` | 未启用 |

`PgVectorResearchMemoryStore` stores `memory_id`, text, embedding vector, and JSON metadata in `insight_graph_memories`. It provides persistence/search plus deletion by memory ID or metadata key/value. `build_memory_record` can generate deterministic offline embeddings for process-local tests and reproducible memory records. When memory context is enabled, Planner retrieves the top 3 similar memory records and uses them as collection hints. Real embedding providers and report-quality eval proof remain future work.

当前 Executor 会执行 planned tools、记录 `tool_call_log`、维护 `global_evidence_pool` 并去重 evidence；relevance 判断默认使用 deterministic/offline 流程，OpenAI-compatible LLM relevance 可通过环境变量配置启用。collection loop 受全局 tool/evidence budgets、section collection round 设置和 optional per-subtask tool rounds 约束；无新 evidence 时会停止后续 tool rounds。Conversation compression 默认关闭；启用后会写入 deterministic summary，保留 evidence IDs、source URLs、tool-call counts 和 findings，供后续长跑 agent loop 使用。

## Relevance Filtering

Relevance filtering 默认关闭。需要过滤工具返回的 evidence 时，可显式启用 deterministic/offline judge：

```bash
INSIGHT_GRAPH_RELEVANCE_FILTER=1 python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_RELEVANCE_FILTER` | `1` / `true` / `yes` 时启用 Executor evidence relevance filtering | 未启用 |
| `INSIGHT_GRAPH_RELEVANCE_JUDGE` | Relevance judge 类型，支持 `deterministic` 或 `openai_compatible` | `deterministic` |
| `INSIGHT_GRAPH_LLM_API_KEY` | OpenAI-compatible provider API key；未设置时回退到 `OPENAI_API_KEY` | - |
| `INSIGHT_GRAPH_LLM_BASE_URL` | OpenAI-compatible `/v1` endpoint；未设置时回退到 `OPENAI_BASE_URL` | - |
| `INSIGHT_GRAPH_LLM_MODEL` | OpenAI-compatible relevance model | `gpt-4o-mini` |
| `INSIGHT_GRAPH_LLM_WIRE_API` | OpenAI-compatible wire API，支持 `chat_completions` 或 `responses`；`responses` 需 provider 支持 `/v1/responses` | `chat_completions` |

默认 `deterministic` judge 不调用真实 LLM，适合离线过滤：未 verified 或缺少 title/source URL/snippet 的 evidence 会被丢弃。需要真实 LLM relevance 判断时，可设置 `INSIGHT_GRAPH_RELEVANCE_JUDGE=openai_compatible`，并通过 API key、base URL 和 model 指向 OpenAI-compatible provider。

## Reporter URL Revalidation

Reporter URL revalidation 默认关闭；`--preset live-research` 会启用它。也可显式设置 `INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=1`。启用后，Reporter 在最终 References 前用 bounded HTTP fetch 验证 verified evidence URLs，将结果写入 `GraphState.url_validation`，并在 References 中标注 `(URL validated)` 或 `(URL validation failed: ...)`。验证失败不会生成替代 URL，也不会伪造引用。

## Snippet-Level Citation Support

Critic 会把 finding 的 verified evidence snippets 写入 `GraphState.citation_support`，并记录 `supporting_snippets`、`matched_terms`、`missing_terms` 和 `support_score`。LLM Reporter 的 prompt 只把 verified evidence snippets 作为允许事实依据，并禁止编造 facts、numbers、sources 或 citations。该边界默认离线 deterministic；LLM Reporter 仍需显式 opt-in。

```bash
INSIGHT_GRAPH_RELEVANCE_FILTER=1 \
INSIGHT_GRAPH_RELEVANCE_JUDGE=openai_compatible \
INSIGHT_GRAPH_LLM_API_KEY=sk-your-relay-key \
INSIGHT_GRAPH_LLM_BASE_URL=https://relay.example.com/v1 \
INSIGHT_GRAPH_LLM_MODEL=gpt-4o-mini \
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

## Observability And Extensibility

Full trace export, MCP-style tool specs, and code execution are explicit opt-in surfaces. By default, trace events omit prompt/completion payloads, MCP specs are empty, and code execution is disabled.

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_MCP_TOOLS_JSON` | JSON array of external MCP-style tool specs `{name, description, endpoint}`; specs are metadata only and are not executed by default | - |
| `INSIGHT_GRAPH_ENABLE_CODE_EXECUTION` | `1` / `true` / `yes` enables restricted arithmetic expression evaluation only | 未启用 |
| `INSIGHT_GRAPH_LLM_TRACE` | `1` / `true` / `yes` 时启用 full LLM JSONL trace logging 到默认 `llm_logs/llm-trace.jsonl` | 未启用 |
| `INSIGHT_GRAPH_LLM_TRACE_PATH` | 设置后启用 full LLM JSONL trace logging 并写入指定文件 | - |

`build_full_trace_event(..., include_payload=True)` is the explicit code-level switch for including prompt/completion payloads in trace exports. `INSIGHT_GRAPH_LLM_TRACE=1` follows the reference `llm_logger` behavior and writes Analyst/Reporter LLM input messages, output text, token usage, duration, and success/error metadata as JSONL. This is diagnostic mode and may persist sensitive prompts or outputs.

`scripts/run_with_llm_log.py` is the reference-style diagnostic runner. It enables full LLM trace logging by default, writes `<timestamp-query>.jsonl` full payload trace files next to `<timestamp-query>.json` safe metadata logs, and prints LLM call/token totals. Use `--safe-log-only` to preserve metadata-only logging without prompt/output trace capture.

## LLM Analyst 配置

Analyst 默认使用 `deterministic` provider，离线且不调用真实 LLM，适合本地开发、测试和 CLI smoke。需要 OpenAI-compatible LLM 生成 evidence-grounded findings 时，可显式 opt-in：

```bash
INSIGHT_GRAPH_ANALYST_PROVIDER=llm \
INSIGHT_GRAPH_LLM_API_KEY=sk-your-relay-key \
INSIGHT_GRAPH_LLM_BASE_URL=https://relay.example.com/v1 \
INSIGHT_GRAPH_LLM_MODEL=gpt-4o-mini \
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_ANALYST_PROVIDER` | Analyst provider 类型，支持默认离线行为的 `deterministic` 或 `llm` opt-in | `deterministic` |
| `INSIGHT_GRAPH_LLM_API_KEY` | OpenAI-compatible provider API key；未设置时回退到 `OPENAI_API_KEY` | - |
| `INSIGHT_GRAPH_LLM_BASE_URL` | OpenAI-compatible `/v1` endpoint；未设置时回退到 `OPENAI_BASE_URL` | - |
| `INSIGHT_GRAPH_LLM_MODEL` | OpenAI-compatible Analyst model | `gpt-4o-mini` |
| `INSIGHT_GRAPH_LLM_WIRE_API` | OpenAI-compatible wire API，支持 `chat_completions` 或 `responses`；`responses` 需 provider 支持 `/v1/responses` | `chat_completions` |

LLM Analyst 只接受引用当前 verified evidence ID 的 JSON findings；`competitive_matrix` 可由 LLM 提供，但每一行必须引用当前 verified evidence ID。缺少矩阵时会用 deterministic 矩阵补齐并保留有效 LLM findings；缺少 key/API、LLM 返回非 JSON、schema 不合法或矩阵引用未 verified/current evidence ID 时，会 fallback 到 deterministic Analyst。测试不调用外部 LLM。

### Qwen/DashScope Provider

Set `INSIGHT_GRAPH_LLM_PROVIDER=qwen` to use DashScope's OpenAI-compatible endpoint. The provider supplies `https://dashscope.aliyuncs.com/compatible-mode/v1` and `qwen-plus` when `INSIGHT_GRAPH_LLM_BASE_URL` and `INSIGHT_GRAPH_LLM_MODEL` are unset. API key resolution is `INSIGHT_GRAPH_LLM_API_KEY`, then `DASHSCOPE_API_KEY`, then `OPENAI_API_KEY`.

Explicit `resolve_llm_config(...)` arguments and `INSIGHT_GRAPH_LLM_*` environment variables override provider defaults. `OPENAI_BASE_URL` is not used as a Qwen endpoint fallback; set `INSIGHT_GRAPH_LLM_BASE_URL` if you need a DashScope-compatible relay. This does not change offline defaults; live LLM use still requires explicit provider/preset configuration.

## LLM Reporter 配置

Reporter 默认使用 deterministic/offline provider，离线且不调用真实 LLM，适合本地开发、测试和 CLI smoke。需要 OpenAI-compatible LLM 生成更专业的报告正文时，可显式 opt-in：

```bash
INSIGHT_GRAPH_REPORTER_PROVIDER=llm \
INSIGHT_GRAPH_LLM_API_KEY=sk-your-relay-key \
INSIGHT_GRAPH_LLM_BASE_URL=https://relay.example.com/v1 \
INSIGHT_GRAPH_LLM_MODEL=gpt-4o-mini \
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_REPORTER_PROVIDER` | Reporter provider 类型，支持默认离线行为的 `deterministic` 或 `llm` opt-in | `deterministic` |
| `INSIGHT_GRAPH_LLM_API_KEY` | OpenAI-compatible provider API key；未设置时回退到 `OPENAI_API_KEY` | - |
| `INSIGHT_GRAPH_LLM_BASE_URL` | OpenAI-compatible `/v1` endpoint；未设置时回退到 `OPENAI_BASE_URL` | - |
| `INSIGHT_GRAPH_LLM_MODEL` | OpenAI-compatible Reporter model | `gpt-4o-mini` |
| `INSIGHT_GRAPH_LLM_WIRE_API` | OpenAI-compatible wire API，支持 `chat_completions` 或 `responses`；`responses` 需 provider 支持 `/v1/responses` | `chat_completions` |

LLM Reporter 只生成报告正文；最终 References 由系统根据 verified evidence 重建。LLM 返回的 fake References 会被丢弃；缺失 `Competitive Matrix` 时会确定性补齐矩阵并保留有效 LLM findings，无法映射到合法引用的矩阵会被替换为 deterministic 矩阵；非法 citation 会 fallback 到 deterministic Reporter。测试不调用外部 LLM。

## LLM Rules Router

InsightGraph can opt into an internal rules router that chooses among user-defined model tiers while keeping the same OpenAI-compatible endpoint configuration.

```bash
INSIGHT_GRAPH_LLM_ROUTER=rules \
INSIGHT_GRAPH_LLM_MODEL_FAST=gpt-4o-mini \
INSIGHT_GRAPH_LLM_MODEL_DEFAULT=gpt-4.1-mini \
INSIGHT_GRAPH_LLM_MODEL_STRONG=gpt-4.1 \
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_LLM_ROUTER` | 设置为 `rules` 时启用内部规则路由；未设置时使用 `INSIGHT_GRAPH_LLM_MODEL` | 未启用 |
| `INSIGHT_GRAPH_LLM_MODEL_FAST` | 短 default-purpose prompt 使用的低成本模型 | 回退到 default tier |
| `INSIGHT_GRAPH_LLM_MODEL_DEFAULT` | 默认模型 tier | `INSIGHT_GRAPH_LLM_MODEL` 或 `gpt-4o-mini` |
| `INSIGHT_GRAPH_LLM_MODEL_STRONG` | Reporter 或长 prompt 使用的强模型 | 回退到 default tier |
| `INSIGHT_GRAPH_LLM_ROUTER_FAST_CHAR_THRESHOLD` | default-purpose prompt 字符数小于等于该值时使用 fast tier | `2000` |
| `INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD` | prompt 字符数超过该值时使用 strong tier | `12000` |

Routing is deterministic and does not call a classifier model. Reporter uses the strong tier. Analyst uses the default tier unless the prompt exceeds the strong threshold. Default-purpose short prompts can use the fast tier.

When routing is enabled, routed Analyst and Reporter LLM call records include safe router metadata in `llm_call_log`: `router`, `router_tier`, `router_reason`, and `router_message_chars`. The log stores only aggregate prompt character count, not prompt text or completions. `--show-llm-log` displays router, tier, and reason columns; JSON output includes all four fields.

LiteLLM Proxy can be used without adding a Python dependency by pointing `INSIGHT_GRAPH_LLM_BASE_URL` at the proxy and using proxy model aliases as tier names:

```bash
INSIGHT_GRAPH_LLM_BASE_URL=http://localhost:4000/v1 \
INSIGHT_GRAPH_LLM_API_KEY=proxy-key \
INSIGHT_GRAPH_LLM_ROUTER=rules \
INSIGHT_GRAPH_LLM_MODEL_FAST=cheap-model-alias \
INSIGHT_GRAPH_LLM_MODEL_DEFAULT=default-model-alias \
INSIGHT_GRAPH_LLM_MODEL_STRONG=strong-model-alias \
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm
```

## Live LLM Preset

默认 CLI 保持 deterministic/offline：

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

要用一个显式开关启用 live pipeline，请配置 LLM endpoint 并使用 `--preset live-llm`：

```bash
INSIGHT_GRAPH_LLM_API_KEY=sk-your-relay-key \
INSIGHT_GRAPH_LLM_BASE_URL=https://relay.example.com/v1 \
INSIGHT_GRAPH_LLM_MODEL=gpt-4o-mini \
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm
```

`live-llm` applies missing runtime defaults for DuckDuckGo search, relevance filtering, OpenAI-compatible relevance judging, LLM Analyst, and LLM Reporter. It does not permanently modify your environment and does not accept API keys as command-line arguments.

`live-llm` does not set `INSIGHT_GRAPH_LLM_WIRE_API`; by default LLM calls use Chat Completions. To test a provider's Responses API support, explicitly set `INSIGHT_GRAPH_LLM_WIRE_API=responses`. If the provider does not support `/v1/responses` or the JSON response format, InsightGraph records the sanitized failure in `llm_call_log` and does not automatically fall back to Chat Completions.

If live `web_search` returns no evidence or fails, the executor records the failed `web_search` attempt and falls back to deterministic `mock_search` evidence. This keeps live smoke/demo runs from producing empty reports while making the fallback visible in `tool_call_log` and `--output-json`.

## LLM Observability

Live LLM paths populate `GraphState.llm_call_log` with metadata for attempted LLM calls. Each record includes the stage (`relevance`, `analyst`, or `reporter`), provider, model, configured wire API when available, success flag, duration in milliseconds, and a short sanitized error summary when a call fails. When the provider returns usage data, records also include nullable `input_tokens`, `output_tokens`, and `total_tokens` fields. InsightGraph does not estimate cost in this version.

The log is in-memory only for this MVP. It does not store prompts, completions, raw response JSON, API keys, authorization headers, or request bodies.

Use `--show-llm-log` to append the in-memory LLM call metadata after the Markdown report:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --show-llm-log
```

The appended table is opt-in and contains only stage, provider, model, router, tier, reason, wire API when available, success, duration, token counts when available, and sanitized error metadata.

Use `--output-json` when scripts need a structured summary instead of Markdown:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

JSON output includes `user_request`, `report_markdown`, `findings`, `competitive_matrix`, `critique`, `tool_call_log`, `llm_call_log`, and `iterations`. It intentionally omits `evidence_pool` and `global_evidence_pool` to avoid dumping fetched snippets. If `--output-json` and `--show-llm-log` are both provided, JSON output takes precedence.

## 计划配置（后续路线图）

默认 CLI 不需要环境变量；真实搜索、relevance、LLM Analyst 等能力通过上文列出的环境变量 opt-in。以下配置项用于后续接入 PostgreSQL、预算控制和更多 provider 时落地。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEFAULT_LLM_PROVIDER` | LLM 提供方（openai / anthropic / qwen / compatible） | openai |
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `ANTHROPIC_API_KEY` | Anthropic API Key | - |
| `QWEN_API_KEY` | Qwen / DashScope API Key | - |
| `SEARCH_PROVIDER` | 搜索提供方（duckduckgo / tavily / serpapi） | duckduckgo |
| `SEARCH_API_KEY` | 搜索服务 API Key | - |
| `DATABASE_URL` | PostgreSQL 连接字符串 | postgresql+asyncpg://localhost/insightgraph |
| `MAX_TOKENS` | 单任务 token 上限 | 500000 |
| `MAX_STEPS` | 最大执行步数（LLM 调用次数） | 100 |
| `MAX_TOOL_CALLS` | 最大工具调用次数 | 200 |
| `MAX_TOOL_ROUNDS` | 单个 subtask 最大工具调用轮数 | 5 |
| `EMBEDDING_DIMENSION` | 向量维度 | 1536 |
