# Run Research Script MVP 设计

## 目标

新增 `scripts/run_research.py`，提供一个稳定的脚本入口来运行 InsightGraph research workflow，并输出 Markdown 报告或结构化 JSON。

第一版是轻量 wrapper：复用现有 `insight_graph.graph.run_research()`、CLI runtime preset 行为和 CLI JSON payload 结构，不新增 workflow 功能。

## 非目标

- 不写报告文件。
- 不创建 `llm_logs/`。
- 不记录 LLM 调用到磁盘。
- 不新增 WebSocket、API 或后台任务能力。
- 不修改 workflow、agent、tool 或 LLM provider 行为。
- 不在异常中输出 raw exception、prompt、completion、headers、API key 或 request body。

## 脚本入口

新增文件：

```text
scripts/run_research.py
```

运行方式：

```bash
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_research.py - < query.txt
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm
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

行为复用 `insight_graph.cli.ResearchPreset` 和 `_apply_research_preset()`：

- `offline` 不设置 live env defaults。
- `live-llm` 使用 `os.environ.setdefault()` 设置现有 live defaults。

第一版不恢复 preset 修改的环境变量，保持与现有 CLI 行为一致。API 已有请求级 env restoration，但该脚本和 CLI 一样是单进程一次性命令。

### `--output-json`

默认输出 Markdown report。

传入 `--output-json` 时，输出结构化 JSON，payload 复用 `insight_graph.cli._build_research_json_payload(state)`，字段与 CLI/API 对齐：

- `user_request`
- `report_markdown`
- `findings`
- `competitive_matrix`
- `critique`
- `tool_call_log`
- `llm_call_log`
- `iterations`

JSON 使用 `indent=2` 和 `ensure_ascii=False`。

## 输出

### Markdown

默认将 `state.report_markdown or ""` 写到 stdout，并确保以单个 newline 结尾。

### JSON

`--output-json` 将 JSON payload 写到 stdout，并以 newline 结尾。

## Exit Codes

- `0`: workflow 运行成功，输出写入成功。
- `1`: workflow 抛出异常。
- `2`: 参数错误、空 query、stdin 读取失败或 stdout 写入失败。

## Error Handling

- workflow 异常 stderr 固定输出：`Research workflow failed.`
- 参数错误由 argparse 输出 usage/error，返回 `2`，不输出 traceback。
- stdin 读取失败 stderr 固定输出：`Failed to read query.`
- stdout 写入失败 stderr 固定输出：`Failed to write output.`
- 不输出 raw exception。

## 测试策略

新增 `tests/test_run_research_script.py`。

全部默认离线，不访问公网。涉及 live preset 的测试只 monkeypatch `run_research()`，不调用真实 LLM 或搜索。

覆盖点：

- positional query 传给 `run_research()`，默认输出 Markdown。
- `-` 从 stdin 读取 query 并 strip。
- 空 query 返回 exit code `2`，不调用 workflow。
- `--output-json` 输出 CLI-aligned payload，包含 `competitive_matrix` 和 `llm_call_log`。
- `--preset offline` 不设置 live defaults。
- `--preset live-llm` 应用现有 CLI live defaults。
- workflow 异常返回 exit code `1`，stderr 固定安全错误，不泄露 raw exception。
- stdout 写入失败返回 exit code `2`，stderr 固定安全错误，不泄露 traceback。
- argparse unknown option 返回 exit code `2`。
- direct script smoke 可在 editable install 后运行。

测试优先直接调用纯 wrapper 函数，例如：

- `main(argv: list[str], stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int`

`main()` 应支持注入 `run_research_func`，便于测试时避免真实 workflow：

```python
main(argv, stdin=stdin, stdout=stdout, stderr=stderr, run_research_func=fake_run_research)
```

## README 更新

在 “脚本状态” 表格中将 `scripts/run_research.py` 标记为当前可用，并说明：

- 运行 research workflow，默认输出 Markdown。
- 支持 stdin `-`。
- 支持 `--preset offline|live-llm`。
- 支持 `--output-json` 输出 CLI/API 对齐结构。

新增用法：

```bash
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_research.py - < query.txt
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

## 验证

实现完成后运行：

```powershell
python -m pytest tests/test_run_research_script.py tests/test_cli.py -q
python -m pytest -q
python -m ruff check .
```

Smoke：

```powershell
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

Markdown smoke 期望包含：

```text
# Research Report
## References
```

JSON smoke 期望包含：

```text
"report_markdown"
"competitive_matrix"
"llm_call_log"
```
