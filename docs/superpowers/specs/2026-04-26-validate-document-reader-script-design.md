# Validate Document Reader Script MVP 设计

## 目标

新增 `scripts/validate_document_reader.py`，离线验证当前 `document_reader` 工具对本地 TXT/Markdown 文件的读取行为、路径安全边界和失败路径。

第一版是自包含 validator：脚本在临时目录中创建 fixtures，临时切换 cwd，直接调用 `insight_graph.tools.document_reader.document_reader()`，不访问公网、不调用 LLM、不修改用户文件。

## 非目标

- 不扩展 `document_reader` 生产功能。
- 不支持 PDF、HTML、分页读取或语义检索验证。
- 不运行完整 research workflow。
- 不读取用户提供的任意目录。
- 不写持久化结果文件。
- 不请求网络。

## 脚本入口

新增文件：

```text
scripts/validate_document_reader.py
```

运行方式：

```bash
python scripts/validate_document_reader.py
python scripts/validate_document_reader.py --markdown
```

第一版不需要 console script entry point。

## 验证模型

脚本创建一个临时 workspace，例如：

```text
<temp>/insightgraph-document-reader-validation/
├── notes.txt
├── market.md
├── appendix.markdown
├── unsupported.pdf
├── empty.txt
├── invalid.txt
└── nested/
    └── deep.md
```

脚本在验证期间临时 `chdir` 到该 workspace，并在退出前恢复原 cwd。

所有文件都由脚本在临时目录中生成；脚本不读取或修改仓库内用户文件。

## Cases

固定 case 列表：

1. `txt_file_success`
   - query: `notes.txt`
   - expected: 返回 1 条 evidence
   - 检查：`title == "notes.txt"`，`source_type == "docs"`，`verified is True`，`source_url` 以 `file://` 开头，snippet 包含 `offline notes`

2. `markdown_file_success`
   - query: `market.md`
   - expected: 返回 1 条 evidence
   - 检查：`title == "market.md"`，snippet 包含 `Markdown market brief`

3. `markdown_suffix_success`
   - query: `appendix.markdown`
   - expected: 返回 1 条 evidence
   - 检查：`title == "appendix.markdown"`，snippet 包含 `Markdown appendix`

4. `nested_file_success`
   - query: `nested/deep.md`
   - expected: 返回 1 条 evidence
   - 检查：`title == "deep.md"`，snippet 包含 `nested document`

5. `unsupported_suffix_returns_empty`
   - query: `unsupported.pdf`
   - expected: 返回 0 条 evidence

6. `missing_file_returns_empty`
   - query: `missing.md`
   - expected: 返回 0 条 evidence

7. `empty_file_returns_empty`
   - query: `empty.txt`
   - expected: 返回 0 条 evidence

8. `invalid_utf8_returns_empty`
   - query: `invalid.txt`
   - expected: 返回 0 条 evidence

9. `outside_root_returns_empty`
   - query: 临时 workspace 之外的文件绝对路径
   - expected: 返回 0 条 evidence

10. `parent_traversal_returns_empty`
    - query: `../outside.md`
    - expected: 返回 0 条 evidence

## Case Payload

每个 case 输出：

```json
{
  "name": "txt_file_success",
  "query": "notes.txt",
  "passed": true,
  "evidence_count": 1,
  "expected_evidence_count": 1,
  "title": "notes.txt",
  "source_type": "docs",
  "verified": true,
  "source_url_scheme": "file",
  "snippet_contains": true,
  "error": null
}
```

对于 expected empty cases，metadata 字段使用 `null`，`snippet_contains` 使用 `null`。

如果 case 执行抛出异常，`passed` 为 `false`，`error` 使用固定安全消息：`Document reader validation case failed.`，不输出 raw exception。

## JSON 输出

默认输出 JSON 到 stdout：

```json
{
  "cases": [
    {
      "name": "txt_file_success",
      "query": "notes.txt",
      "passed": true,
      "evidence_count": 1,
      "expected_evidence_count": 1,
      "title": "notes.txt",
      "source_type": "docs",
      "verified": true,
      "source_url_scheme": "file",
      "snippet_contains": true,
      "error": null
    }
  ],
  "summary": {
    "case_count": 10,
    "passed_count": 10,
    "failed_count": 0,
    "all_passed": true,
    "total_evidence_count": 4
  }
}
```

JSON 使用 `indent=2` 和 `ensure_ascii=False`。

## Markdown 输出

`--markdown` 输出 GitHub-flavored Markdown：

```markdown
# Document Reader Validation

| Case | Passed | Evidence | Expected | Title | Source type | Verified | URL scheme | Snippet check | Error |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| txt_file_success | true | 1 | 1 | notes.txt | docs | true | file | true |  |

## Summary

| Cases | Passed | Failed | All passed | Total evidence |
| ---: | ---: | ---: | --- | ---: |
| 10 | 10 | 0 | true | 4 |
```

Markdown table cells需要 escape `|` 并压缩换行。

## Exit Codes

- `0`: 所有 cases 通过。
- `1`: 一个或多个 cases 失败。
- `2`: 参数错误、无法创建临时 workspace 或输出写入失败。

## Error Handling

- case 内异常不会中断整个验证；对应 case 标记失败并写固定安全错误。
- 临时目录创建、fixture 写入、cwd 切换或 stdout 写入失败属于脚本级错误，返回 `2`。
- 脚本级错误写 stderr，格式固定为：`Document reader validation failed: <safe message>`。
- 不输出 traceback。

## 测试策略

新增 `tests/test_validate_document_reader.py`。

全部测试离线，不访问公网。

覆盖点：

- `run_validation()` 返回 10 个固定 cases。
- success cases 返回 expected evidence metadata。
- unsupported、missing、empty、invalid UTF-8、outside root、parent traversal cases 返回 empty 且 passed。
- summary 统计 `case_count`、`passed_count`、`failed_count`、`all_passed`、`total_evidence_count`。
- cwd 在成功和异常路径后恢复。
- case 异常输出固定安全错误，不包含 raw exception。
- 默认 JSON output 包含 `cases` 和 `summary`。
- `--markdown` output 包含 `# Document Reader Validation` 和 `## Summary`。
- Markdown escaping 覆盖 `|` 和换行。
- stdout 写入失败返回 exit code 2，不输出 traceback。

测试优先直接调用纯函数，例如：

- `run_validation() -> dict`
- `format_markdown(payload: dict) -> str`
- `main(argv: list[str], stdout: TextIO, stderr: TextIO) -> int`

## README 更新

在 “脚本状态” 表格中将 `scripts/validate_document_reader.py` 标记为当前可用，并说明：

- 离线验证当前本地 TXT/Markdown document_reader 行为。
- 不支持 PDF/HTML。
- 默认 JSON 输出，`--markdown` 输出表格。

新增用法：

```bash
python scripts/validate_document_reader.py
python scripts/validate_document_reader.py --markdown
```

## 验证

实现完成后运行：

```powershell
python -m pytest tests/test_validate_document_reader.py tests/test_validate_sources.py -q
python -m pytest -q
python -m ruff check .
```

Smoke：

```powershell
python scripts/validate_document_reader.py
python scripts/validate_document_reader.py --markdown
```

JSON smoke 期望包含：

```text
"all_passed": true
"case_count": 10
```

Markdown smoke 期望包含：

```text
# Document Reader Validation
## Summary
```
