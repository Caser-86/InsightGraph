# Validate Sources Script MVP 设计

## 目标

新增 `scripts/validate_sources.py`，离线校验 InsightGraph Markdown 报告中的 citation 与 References 结构，作为报告质量守门脚本。

第一版只解析 Markdown，不请求网络，不验证 URL 实际可访问。

## 非目标

- 不联网请求 URL。
- 不运行 `run_research()`。
- 不读取 API 响应 JSON。
- 不修改报告文件。
- 不自动修复 citation 或 References。
- 不支持复杂 Markdown AST，只做当前 Reporter 输出格式和常见 Markdown 变体的轻量解析。

## 脚本入口

新增文件：

```text
scripts/validate_sources.py
```

运行方式：

```bash
python scripts/validate_sources.py report.md
python scripts/validate_sources.py - < report.md
python scripts/validate_sources.py report.md --markdown
```

第一版不需要 console script entry point。

## 输入

单个 positional 参数：

- 文件路径：读取 UTF-8 Markdown 文件。
- `-`：从 stdin 读取 Markdown。

输入为空字符串视为可解析报告，但会产生 `missing_references_section` issue。

## References 解析

当前 Reporter 输出 References 格式：

```markdown
## References

[1] Cursor Pricing. https://cursor.com/pricing
[2] GitHub Copilot Documentation. https://docs.github.com/en/copilot
```

解析规则：

- References section 从 H2-H6 heading `References` 或 `Sources` 开始，大小写不敏感，允许尾随空格和 closing hashes。
- References section 到下一个同级或更高级 ATX heading 结束；没有下一个 heading 则到文档末尾。
- 支持 reference 行格式：`[N] Title. URL`。
- `N` 必须为正整数。
- URL 取 reference 行中的最后一个非空 whitespace-separated token。
- URL 必须以 `http://` 或 `https://` 开头，否则产生 `invalid_reference_url`。
- 同一个 reference number 重复出现时产生 `duplicate_reference`。

## Citation 解析

正文 citation 格式：`[N]`。

规则：

- 只统计 References section 之外的 `[N]`。
- `N` 必须为正整数。
- 同一编号出现多次只算一次 used reference。
- 不支持范围 citation，如 `[1-3]`；第一版会忽略这种格式。

## Issue Types

固定 issue types：

- `missing_references_section`: report 中没有 References/Sources section。
- `missing_reference`: 正文 citation `[N]` 没有对应 References 条目。
- `unused_reference`: References 中 `[N]` 没有被正文 citation 使用。
- `invalid_reference_url`: References 条目的 URL 不是 `http://` 或 `https://`。
- `duplicate_reference`: References 中同一个编号出现多次。

每个 issue 包含：

```json
{
  "type": "missing_reference",
  "reference": 3,
  "message": "Citation [3] has no matching reference."
}
```

`reference` 对于 `missing_references_section` 为 `null`。

## JSON 输出

默认输出 JSON 到 stdout。

成功无 issue 示例：

```json
{
  "ok": true,
  "citation_count": 2,
  "reference_count": 2,
  "issues": []
}
```

有 issue 示例：

```json
{
  "ok": false,
  "citation_count": 2,
  "reference_count": 1,
  "issues": [
    {
      "type": "missing_reference",
      "reference": 2,
      "message": "Citation [2] has no matching reference."
    }
  ]
}
```

JSON 使用 `indent=2` 和 `ensure_ascii=False`。

## Markdown 输出

`--markdown` 输出 GitHub-flavored Markdown。

格式：

```markdown
# Source Validation

| OK | Citations | References | Issues |
| --- | ---: | ---: | ---: |
| true | 2 | 2 | 0 |
```

有 issue 时追加：

```markdown
## Issues

| Type | Reference | Message |
| --- | ---: | --- |
| missing_reference | 2 | Citation [2] has no matching reference. |
```

Markdown table cells需要 escape `|` 并压缩换行。

## Exit Codes

- `0`: 无 issue。
- `1`: 有一个或多个 issue。
- `2`: 输入文件无法读取、参数错误或 I/O 错误。

注意：stdin 输入 `-` 读取成功但内容为空时不属于 I/O 错误，返回 `1`，并输出 `missing_references_section`。

## 测试策略

新增 `tests/test_validate_sources.py`。

全部测试离线，不访问公网。

覆盖点：

- valid report 返回 `ok=true`、exit code 0。
- missing References section 产生 `missing_references_section`、exit code 1。
- citation 无对应 reference 产生 `missing_reference`。
- reference 未被正文引用产生 `unused_reference`。
- invalid URL 产生 `invalid_reference_url`。
- duplicate reference number 产生 `duplicate_reference`。
- citation 统计忽略 References section 内的 `[N]`。
- stdin `-` 输入路径工作。
- missing file 返回 exit code 2，错误输出不包含 traceback。
- Markdown output 包含 summary table 和 issue table。
- Markdown escaping 覆盖 `|` 和换行。

测试优先直接调用脚本中的纯函数，例如：

- `validate_report(markdown: str) -> dict`
- `format_markdown(payload: dict) -> str`
- `main(argv: list[str], stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int`

## README 更新

在 “脚本状态” 表格中将 `scripts/validate_sources.py` 标记为当前可用，并说明：

- 离线校验 Markdown 报告 citation 与 References。
- 支持文件路径或 stdin `-`。
- 默认 JSON 输出，`--markdown` 输出表格。
- 不联网校验 URL 可访问性。

## 验证

实现完成后运行：

```powershell
python -m pytest tests/test_validate_sources.py tests/test_benchmark_research.py -q
python -m pytest -q
python -m ruff check .
```

Smoke：

```powershell
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" | python scripts/validate_sources.py -
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" | python scripts/validate_sources.py - --markdown
```

JSON smoke 期望包含：

```text
"ok": true
"issues": []
```

Markdown smoke 期望包含：

```text
# Source Validation
| true |
```
