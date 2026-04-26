# Run With LLM Log Script MVP 设计

## 目标

新增 `scripts/run_with_llm_log.py`，运行 InsightGraph research workflow，并把本次运行的安全 LLM metadata 写入 `llm_logs/` 中的 JSON 文件。

第一版复用现有 workflow、runtime preset 和 observability 结构，只记录安全 metadata，不记录 prompt、completion、raw response、headers、API key、request body 或 raw exception payload。

## 非目标

- 不记录 prompt、completion 或 raw LLM response。
- 不记录 API key、headers、request body 或 provider raw exception。
- 不实现 prompt replay。
- 不新增 LLM provider 或 workflow 行为。
- 不实现 WebSocket、前端、持久化或后台任务。
- 不强制启用 live LLM；`--preset live-llm` 只复用现有 CLI preset 行为。

## 脚本入口

新增文件：

```text
scripts/run_with_llm_log.py
```

运行方式：

```bash
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_with_llm_log.py - < query.txt
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot" --log-dir tmp_llm_logs
```

第一版不需要 console script entry point。

## 输入

单个 positional 参数：

- 普通字符串：作为 research query。
- `-`：从 stdin 读取完整 query。

输入处理：

- query 会 `strip()`。
- strip 后为空返回 exit code `2`。
- 空 query stderr 固定输出：`Research query must not be empty.`

## Options

### `--preset`

允许值：

- `offline`，默认值。
- `live-llm`。

行为复用 `insight_graph.cli.ResearchPreset` 和 `_apply_research_preset()`。

`offline` 不清理已存在的 opt-in 环境变量，保持与 CLI 和 `scripts/run_research.py` 一致；如果运行环境已有 LLM/tool opt-in env vars，仍会被 workflow 尊重。

### `--log-dir`

默认：`llm_logs`。

规则：

- 相对路径按当前 cwd 解析。
- 脚本会创建目录。
- 路径存在但不是目录时返回 exit code `2`。
- 第一版允许 cwd 内任意相对目录和绝对目录；使用者显式指定路径即表示授权写入该目录。

## 输出

### stdout

默认将 `state.report_markdown or ""` 写到 stdout，并确保以单个 newline 结尾，保留其他 trailing whitespace。

报告后追加一行 log 文件位置：

```text
LLM log written to: llm_logs/20260426T120000Z-compare-cursor-opencode-and-github-copilot.json
```

### Log 文件

文件名格式：

```text
YYYYMMDDTHHMMSSZ-<query-slug>.json
```

规则：

- timestamp 使用 UTC。
- query slug 由 lower-case query 生成，只保留 `[a-z0-9]`，其他字符折叠为 `-`。
- slug 最长 60 字符，空 slug 使用 `research`。
- 如果目标文件已存在，追加 `-2`、`-3` 等 suffix，避免覆盖。

## Log Schema

JSON 使用 `indent=2` 和 `ensure_ascii=False`。

字段：

```json
{
  "query": "Compare Cursor, OpenCode, and GitHub Copilot",
  "preset": "offline",
  "report_markdown_length": 1200,
  "finding_count": 2,
  "competitive_matrix_row_count": 3,
  "tool_call_log": [
    {
      "subtask_id": "collect",
      "tool_name": "mock_search",
      "query": "Compare Cursor, OpenCode, and GitHub Copilot",
      "evidence_count": 3,
      "filtered_count": 0,
      "success": true,
      "error": null
    }
  ],
  "llm_call_log": [
    {
      "stage": "reporter",
      "provider": "llm",
      "model": "gpt-5.4",
      "wire_api": "chat_completions",
      "success": true,
      "duration_ms": 100,
      "input_tokens": 10,
      "output_tokens": 20,
      "total_tokens": 30,
      "error": null
    }
  ],
  "iterations": 0
}
```

不包含：

- `report_markdown` 全文。
- `findings` 全文。
- `competitive_matrix` 全文。
- `evidence_pool` 或 `global_evidence_pool`。
- prompt、completion、raw response、headers、API key、request body。

## Exit Codes

- `0`: workflow 成功，report 输出成功，log 文件写入成功。
- `1`: workflow 抛出异常。
- `2`: 参数错误、空 query、stdin 读取失败、log 目录错误、log 写入失败或 stdout 写入失败。

## Error Handling

- workflow 异常 stderr 固定输出：`Research workflow failed.`
- 参数错误由 argparse 输出 usage/error，返回 `2`，不输出 traceback。
- stdin 读取失败 stderr 固定输出：`Failed to read query.`
- log 目录错误 stderr 固定输出：`Failed to prepare LLM log directory.`
- log 写入失败 stderr 固定输出：`Failed to write LLM log.`
- stdout 写入失败 stderr 固定输出：`Failed to write output.`
- 不输出 raw exception。

如果 workflow 成功但 log 写入失败，不输出 report，返回 `2`。这样避免用户以为本次运行已有 log artifact。

## 测试策略

新增 `tests/test_run_with_llm_log_script.py`。

全部默认离线，不访问公网。涉及 live preset 的测试只 monkeypatch `run_research()`，不调用真实 LLM 或搜索。

覆盖点：

- positional query 传给 workflow，stdout 输出 Markdown 和 log path。
- `-` 从 stdin 读取 query 并 strip。
- 空 query 返回 exit code `2`，不调用 workflow。
- 默认 `llm_logs` 目录创建和 JSON 文件写入。
- `--log-dir` 指定目录。
- 文件名 slug 和 collision suffix。
- log JSON 包含安全 schema：query、preset、summary counts、tool_call_log、llm_call_log、iterations。
- log JSON 不包含 `report_markdown`、`findings` 全文、`evidence_pool`、prompt、completion、API key。
- `--preset offline` 不设置 live defaults。
- `--preset live-llm` 应用现有 CLI live defaults。
- workflow 异常返回 exit code `1`，不写 log，不泄露 raw exception。
- log dir 是文件时返回 exit code `2`。
- log 写入失败返回 exit code `2`，不输出 report。
- stdout 写入失败返回 exit code `2`。
- argparse unknown option 返回 exit code `2`。

测试优先直接调用 wrapper 函数：

```python
main(argv, stdin=stdin, stdout=stdout, stderr=stderr, run_research_func=fake_run_research)
```

为稳定测试，`main()` 应支持注入 clock：

```python
main(
    ["Compare Cursor, OpenCode, and GitHub Copilot"],
    stdin=stdin,
    stdout=stdout,
    stderr=stderr,
    run_research_func=fake_run_research,
    now_func=lambda: datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc),
)
```

## README 更新

在 “脚本状态” 表格中将 `scripts/run_with_llm_log.py` 标记为当前可用，并说明：

- 运行 research workflow。
- stdout 输出 Markdown。
- 将安全 LLM metadata 写入 `llm_logs/`。
- 不记录 prompt/completion/raw response/API key。

新增用法：

```bash
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_with_llm_log.py - < query.txt
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot" --log-dir tmp_llm_logs
```

## 验证

实现完成后运行：

```powershell
python -m pytest tests/test_run_with_llm_log_script.py tests/test_run_research_script.py -q
python -m pytest -q
python -m ruff check .
```

Smoke：

```powershell
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot" --log-dir tmp_llm_logs
```

stdout 期望包含：

```text
# InsightGraph Research Report
LLM log written to:
```

log JSON 期望包含：

```text
"llm_call_log"
"tool_call_log"
```

并且不包含：

```text
prompt
completion
api_key
```
