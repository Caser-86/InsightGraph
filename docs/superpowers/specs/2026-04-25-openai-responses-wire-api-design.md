# OpenAI Responses Wire API 设计

## 目标

让 InsightGraph 的 OpenAI-compatible LLM 客户端支持显式切换到 Responses API wire format，同时保持现有 Chat Completions 行为作为默认值。

这项能力解决一个实际配置差异：部分 OpenAI-compatible provider 使用 `responses` wire API，而当前 InsightGraph 只调用 `/v1/chat/completions`。新能力必须是 opt-in，不能改变默认 offline/deterministic 行为，也不能破坏当前 live-llm preset。

## 非目标

- 不新增 CLI API key 参数。
- 不自动推断 provider 应该使用哪种 wire API。
- 不切换默认 LLM wire format。
- 不记录 prompt、completion、headers、request body、raw response 或 API key。
- 不实现 OpenAI Assistants、tools/function calling、streaming 或 reasoning 参数。

## 配置

新增 `LLMConfig.wire_api: str`。

配置来源：

- 显式参数 `resolve_llm_config(wire_api=...)` 优先。
- 环境变量 `INSIGHT_GRAPH_LLM_WIRE_API` 次之。
- 默认值为 `chat_completions`。

支持值：

- `chat_completions`
- `responses`

非法值应尽早失败，错误信息包含 `wire_api` 和支持值，便于用户修正配置。

## 客户端行为

保留现有 `OpenAICompatibleChatClient` 对外接口：

- `complete_json(messages) -> str`
- `complete_json_with_usage(messages) -> ChatCompletionResult`

内部根据 `self.config.wire_api` 分支：

- `chat_completions` 继续调用 `client.chat.completions.create(...)`。
- `responses` 调用 `client.responses.create(...)`。

这样 analyst、reporter、relevance judge 和 observability helper 都无需改调用方式。

## Chat Completions 请求保持不变

现有请求结构不变：

```python
client.chat.completions.create(
    model=config.model,
    messages=[message.model_dump() for message in messages],
    response_format={"type": "json_object"},
    temperature=0,
)
```

现有 usage 映射保持不变：

- `usage.prompt_tokens` -> `input_tokens`
- `usage.completion_tokens` -> `output_tokens`
- `usage.total_tokens` -> `total_tokens`

## Responses 请求

Responses API 请求使用现有 `ChatMessage` 输入，不引入新 message model。

请求结构：

```python
client.responses.create(
    model=config.model,
    input=[message.model_dump() for message in messages],
    text={"format": {"type": "json_object"}},
    temperature=0,
)
```

如果某些兼容 provider 不支持 `text.format`，这是 provider compatibility 问题，不在第一版里自动 fallback。第一版优先保持请求语义明确：调用方要求 JSON，provider 应返回 JSON 文本。

## Responses 返回解析

Responses API 的正文提取顺序：

1. 优先读取 `response.output_text`。
2. 如果没有 `output_text`，遍历 `response.output[*].content[*].text`，拼接非空文本。
3. 如果仍没有正文，抛出 `ValueError("LLM response content is required")`。

usage 映射：

- `usage.input_tokens` -> `input_tokens`
- `usage.output_tokens` -> `output_tokens`
- `usage.total_tokens` -> `total_tokens`

如果 provider 不返回 usage，对应字段保持 `None`，与当前行为一致。

## 错误处理和安全

- 缺少 API key 继续抛出 `ValueError("LLM api_key is required")`。
- 上游 API 异常继续向上抛出，由 analyst/reporter/relevance 现有 fallback 和 observability 逻辑处理。
- 空响应内容继续抛出 `ValueError`。
- 不把 raw response、prompt、completion、API key 或 headers 写入 `LLMCallRecord`。

## 测试策略

新增和调整单元测试，全部使用 fake client，不访问公网。

覆盖点：

- 默认 `resolve_llm_config()` 返回 `wire_api="chat_completions"`。
- `INSIGHT_GRAPH_LLM_WIRE_API=responses` 被读取。
- 显式参数覆盖环境变量。
- 非法 `wire_api` 抛出清晰错误。
- 默认 chat completions 请求结构保持不变。
- responses wire API 调用 `client.responses.create(...)`。
- responses wire API 能读取 `output_text`。
- responses wire API 能 fallback 读取 nested output content text。
- responses usage 映射到 `ChatCompletionResult`。
- `complete_json()` 在 responses wire API 下仍只返回 content string。

## 验证

实现完成后运行：

```powershell
python -m pytest tests/test_llm_config.py tests/test_llm_client.py -q
python -m pytest -q
python -m ruff check .
```

可选 live smoke 使用显式 env：

```powershell
$env:INSIGHT_GRAPH_LLM_WIRE_API = "responses"
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --output-json
```

live smoke 期望：输出 parseable JSON；`llm_call_log` 仍包含安全 metadata 和 token fields；默认不暴露 prompt、completion 或 secret。
