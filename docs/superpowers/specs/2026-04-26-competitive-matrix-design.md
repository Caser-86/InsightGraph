# Competitive Matrix MVP 设计

## 目标

为 InsightGraph 增加第一版结构化竞品矩阵能力，让默认离线报告稳定包含 `Competitive Matrix` Markdown 表格，并让 `--output-json` 自动暴露矩阵数据。

第一版以 deterministic/offline 为主，不依赖真实 LLM，不做评分、排名、定价抽取或复杂实体消歧。

## 非目标

- 不实现复杂 entity resolution。
- 不从网页中抽取精确定价、SKU 或数值指标。
- 不做加权评分、排名或 winner 判断。
- 不改变默认 CLI 数据源；默认仍使用 `mock_search`。
- 不要求 LLM Reporter 自行生成矩阵。
- 不新增外部依赖。

## State Schema

在 `src/insight_graph/state.py` 新增模型：

```python
class CompetitiveMatrixRow(BaseModel):
    product: str
    positioning: str
    strengths: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
```

在 `GraphState` 新增字段：

```python
competitive_matrix: list[CompetitiveMatrixRow] = Field(default_factory=list)
```

Pydantic JSON serialization 会让 CLI `--output-json` 自动包含 `competitive_matrix`，因为 payload 已从 state fields 构造 findings/critique/tool logs；实现需显式加入该字段，避免 API 消费方缺失矩阵。

## Deterministic Analyst 行为

`_analyze_evidence_deterministic(state)` 除生成现有 `findings` 外，还生成 `state.competitive_matrix`。

矩阵生成规则：

1. 只使用 `state.evidence_pool` 中 `verified=True` 的 evidence。
2. 从 `state.user_request` 和 evidence `title/snippet` 中识别产品名。
3. 第一版内置候选产品名匹配：
   - `Cursor`
   - `OpenCode`
   - `Claude Code`
   - `GitHub Copilot`
   - `Codeium`
   - `Windsurf`
4. 大小写不敏感匹配，但输出使用规范 product 名称。
5. 每个产品最多生成一行。
6. 每行最多引用 3 个 verified evidence IDs。
7. 如果没有识别到任何产品，但存在 verified evidence，则生成一行 `General market evidence`，引用前 3 个 evidence IDs。
8. 如果没有 verified evidence，则 `competitive_matrix=[]`。

`positioning` 由 evidence source type 和 snippet/title 的简单启发式生成：

- 有 `github` evidence：`Open-source or developer ecosystem signal`
- 有 `docs` evidence：`Documented product or local research source`
- 有 `news` evidence：`Market/news activity signal`
- 有 `official_site` evidence：`Official product positioning signal`
- 其他：`Evidence-backed product signal`

`strengths` 第一版最多 3 条，每条是简短 deterministic 标签：

- `Official/documented source coverage`
- `Repository or developer ecosystem evidence`
- `News or launch activity evidence`
- `Local research material available`
- `Verified evidence available`

标签由该产品关联 evidence 的 `source_type` 决定，避免生成未验证的主观判断。

## LLM Analyst 兼容

LLM Analyst 第一版可选解析响应中的 `competitive_matrix` 字段；缺失时使用 deterministic matrix builder 从 evidence 生成矩阵。

LLM 响应允许形状：

```json
{
  "findings": [
    {
      "title": "Developer tools show differentiated positioning",
      "summary": "Verified product and repository evidence indicates distinct developer workflows.",
      "evidence_ids": ["cursor-pricing"]
    }
  ],
  "competitive_matrix": [
    {
      "product": "Cursor",
      "positioning": "Official product positioning signal",
      "strengths": ["Official/documented source coverage"],
      "evidence_ids": ["cursor-pricing"]
    }
  ]
}
```

Validation rules：

- `competitive_matrix` 可以缺失。
- 如果存在，必须是 list。
- 每行必须是 object。
- `product` 和 `positioning` 必须是非空字符串。
- `strengths` 必须是字符串列表，最多 5 条；空列表允许。
- `evidence_ids` 必须是 verified evidence IDs 的非空字符串列表，且全部属于当前 verified evidence pool。
- 无效矩阵字段导致 LLM Analyst fallback 到 deterministic analyst，而不是部分接受。

## Reporter 行为

Deterministic Reporter 在 `## Key Findings` 之后、`## Critic Assessment` 之前插入：

```markdown
## Competitive Matrix

| Product | Positioning | Strengths | Evidence |
| --- | --- | --- | --- |
| Cursor | Official product positioning signal | Official/documented source coverage | [1], [2] |
```

规则：

- 只渲染至少有一个可映射 verified citation 的矩阵行。
- Evidence 列使用现有 reference numbers：`[N]`。
- `Strengths` 使用 `; ` 连接。
- 所有表格单元格需要 escape `|` 并压缩换行。
- 如果没有可渲染行，则省略整个 `Competitive Matrix` section。

LLM Reporter 不需要自行生成矩阵。若 LLM 返回 markdown 已包含 `## Competitive Matrix`，Reporter 不重复插入；若缺失且 `state.competitive_matrix` 有可引用行，则在 LLM body 的 `## Key Findings` section 后插入 deterministic matrix section，再追加 references。

## CLI JSON

`_build_research_json_payload(state)` 新增：

```python
"competitive_matrix": [row.model_dump(mode="json") for row in state.competitive_matrix]
```

这样默认 CLI `--output-json` 能直接供后续 API/benchmark 使用。

## README 更新

README 更新当前 MVP 能力：

- Analyst 生成结构化 `competitive_matrix`。
- Reporter 输出 `Competitive Matrix` Markdown 表格。
- `--output-json` 包含 `competitive_matrix`。
- 明确第一版矩阵是 evidence-backed deterministic MVP，不做排名、评分、精确定价抽取。

## 测试策略

全部测试离线运行。

覆盖点：

- `GraphState` 默认 `competitive_matrix=[]`。
- deterministic Analyst 对包含 Cursor/GitHub Copilot/OpenCode evidence 的 state 生成矩阵行。
- deterministic Analyst 只引用 verified evidence。
- deterministic Analyst 无产品名但有 verified evidence 时生成 `General market evidence` 行。
- deterministic Analyst 无 verified evidence 时矩阵为空。
- LLM Analyst 能解析合法 `competitive_matrix`。
- LLM Analyst 对未知/未 verified evidence IDs fallback deterministic。
- deterministic Reporter 渲染 `## Competitive Matrix` 表格，并使用正确 citations。
- deterministic Reporter 无可引用矩阵行时省略 section。
- LLM Reporter body 缺少矩阵时插入 deterministic matrix section。
- LLM Reporter body 已含 `## Competitive Matrix` 时不重复插入。
- CLI `--output-json` payload 包含 `competitive_matrix`。

## 验证

实现完成后运行：

```powershell
python -m pytest tests/test_agents.py tests/test_cli.py tests/test_graph.py -q
python -m pytest -q
python -m ruff check .
```

CLI smoke：

```powershell
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

期望 JSON 含 `competitive_matrix` 字段，默认 Markdown report 含 `## Competitive Matrix`。
