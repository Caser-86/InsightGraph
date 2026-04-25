# LLM Wire API Observability 设计

## 目标

让 InsightGraph 的 LLM 调用日志明确显示每次 OpenAI-compatible 调用使用的 wire API：`chat_completions` 或 `responses`。

上一阶段已经支持 `INSIGHT_GRAPH_LLM_WIRE_API=responses`，但 live smoke 失败时，当前 `llm_call_log` 只能看到 stage、provider、model、success、duration、tokens 和 sanitized error，无法直接判断失败发生在哪种 wire API 上。新增 `wire_api` 元数据可以让 CLI、JSON 输出和调试日志更清晰，同时保持安全边界。

## 非目标

- 不自动 fallback 到 Chat Completions。
- 不改变默认 wire API；默认仍是 `chat_completions`。
- 不记录 base URL、endpoint path、headers、prompt、completion、raw response、request body 或 API key。
- 不新增持久化日志或外部 telemetry。
- 不修改 LLM provider 选择逻辑。

## 数据模型

`LLMCallRecord` 新增字段：

```python
wire_api: str | None = None
```

字段语义：

- `chat_completions`：调用 OpenAI-compatible Chat Completions wire API。
- `responses`：调用 OpenAI-compatible Responses wire API。
- `None`：调用方没有可用 wire API 元数据，例如 legacy fake client 或未来非 OpenAI-compatible client。

使用 nullable 字段可以保持测试 fake client 和历史日志模型的兼容性。

## Observability Helper

`build_llm_call_record()` 新增可选参数：

```python
wire_api: str | None = None
```

它只把传入值写入 `LLMCallRecord.wire_api`，不推断、不读取环境变量，也不验证 provider 配置。wire API 校验仍属于 `LLMConfig` 的责任。

## 调用点

Analyst、Reporter、Relevance judge 在记录 LLM 调用时，从 LLM client 上安全读取 wire API：

```python
wire_api = getattr(getattr(llm_client, "config", None), "wire_api", None)
```

然后传入 `build_llm_call_record(wire_api=wire_api, ...)`。

这样做避免要求所有 fake/legacy client 都实现 `config` 属性。

## CLI 输出

`--show-llm-log` 表格新增 `Wire API` 列。

列顺序：

```text
Stage | Provider | Model | Wire API | Success | Duration ms | Input tokens | Output tokens | Total tokens | Error
```

如果 `wire_api` 为 `None`，单元格为空字符串。输出仍然不包含 prompt、completion、raw payload 或 secret。

## JSON 输出

`--output-json` 已经通过 `LLMCallRecord.model_dump(mode="json")` 输出日志，因此新增字段会自动出现在每条 `llm_call_log` 记录中。

示例：

```json
{
  "stage": "analyst",
  "provider": "llm",
  "model": "gpt-5.4",
  "wire_api": "responses",
  "success": false,
  "duration_ms": 2200,
  "input_tokens": 102,
  "output_tokens": 12,
  "total_tokens": 114,
  "error": "ValueError: LLM call failed."
}
```

## README 更新

README 的 LLM 配置区补充 `INSIGHT_GRAPH_LLM_WIRE_API`：

- 默认值：`chat_completions`
- 可选值：`chat_completions`、`responses`
- `responses` 是显式 opt-in。
- provider 不支持 `/v1/responses` 或不支持当前 JSON response format 时，InsightGraph 会记录安全失败信息，不自动 fallback。

Live LLM preset 文档也补充说明：preset 不会设置 `INSIGHT_GRAPH_LLM_WIRE_API`，因此默认仍走 Chat Completions；用户必须显式设置 `responses` 才会启用新 wire API。

## 测试策略

全部测试使用 fake client，不访问公网。

覆盖点：

- `LLMCallRecord` 默认 `wire_api is None`。
- `build_llm_call_record(wire_api="responses")` 写入字段。
- Analyst LLM 调用记录 `wire_api`。
- Reporter LLM 调用记录 `wire_api`。
- Relevance judge LLM 调用记录 `wire_api`。
- `--show-llm-log` 表格包含 `Wire API` 列和值。
- 空 LLM log 也显示 `Wire API` 表头。
- `--output-json` 的 `llm_call_log` 包含 `wire_api` 字段。

## 验证

实现完成后运行：

```powershell
python -m pytest tests/test_state.py tests/test_agents.py tests/test_relevance.py tests/test_cli.py -q
python -m pytest -q
python -m ruff check .
```

可选 live smoke：

```powershell
$env:INSIGHT_GRAPH_LLM_WIRE_API = "responses"
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --output-json
```

期望：JSON 可解析；`llm_call_log[*].wire_api` 显示 `responses`；失败时只记录 sanitized error，不泄露 prompt、response、endpoint 或 secret。
