# DDGS 迁移设计

## 目标

将已改名的旧依赖 `duckduckgo-search` 替换为新包 `ddgs`，让 live search 不再输出运行时警告：

```text
This package (`duckduckgo_search`) has been renamed to `ddgs`! Use `pip install ddgs` instead.
```

## 非目标

- 不修改搜索 provider 的配置名称，`INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo` 继续有效。
- 不修改 `SearchResult` 字段或 `source` 标签。
- 不修改现有 fallback 到 `mock_search` 的行为。
- 不为 `duckduckgo_search` 保留兼容 fallback import。
- 不修改 `live-llm` preset 默认值。

## 决策

采用 **直接替换**：

- 从 `pyproject.toml` 删除 `duckduckgo-search>=6.0.0`。
- 向 `pyproject.toml` 增加 `ddgs>=9.0.0`。
- 将 `_create_duckduckgo_client()` 改为从 `ddgs` 导入 `DDGS`。

不保留旧包兼容导入。项目还处于早期阶段，保留 deprecated import path 会增加不必要的复杂度，也可能让 warning 继续出现。

## 当前兼容性检查

当前本地环境中两个包都已安装。`ddgs` 暴露了当前 adapter 使用的同一类接口：`DDGS().text(query, max_results=limit)`。

- `ddgs` 已安装：是
- `from ddgs import DDGS`：可用
- `DDGS().text`：存在

现有 fake-client 测试已经能在不访问公网的情况下覆盖 adapter 映射行为。

## 实现设计

修改 `pyproject.toml`：

```toml
dependencies = [
  "beautifulsoup4>=4.12.0",
  "ddgs>=9.0.0",
  ...
]
```

修改 `src/insight_graph/tools/search_providers.py`：

```python
def _create_duckduckgo_client() -> Any:
    from ddgs import DDGS

    return DDGS()
```

其他路径保持不变：

- `DuckDuckGoSearchProvider` 类名不变。
- `get_search_provider("duckduckgo")` 行为不变。
- live search 映射出的 `SearchResult.source` 仍为 `"duckduckgo"`。
- 搜索失败或空结果仍返回 `[]`，继续交给 executor 的 `mock_search` fallback 处理。

## 测试

单元测试只使用 fake client，不访问公网。

覆盖范围：

- 现有 DuckDuckGo result 映射测试继续通过。
- 现有 provider 选择测试继续通过。
- `_create_duckduckgo_client()` 从 `ddgs` 导入 `DDGS`，不再使用 `duckduckgo_search`。
- 全量测试继续通过。
- live smoke 不再输出 `duckduckgo_search` rename warning。

最小验证命令：

```bash
python -m pytest tests/test_search_providers.py tests/test_web_search.py -q
python -m ruff check src/insight_graph/tools/search_providers.py tests/test_search_providers.py
```

最终验证命令：

```bash
python -m pytest -v
python -m ruff check .
```

实现后 live smoke：

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --output-json
```

预期 live smoke 结果：

- 不再出现 `duckduckgo_search` rename warning。
- workflow 仍能完成。
- 如果 live search 没有返回 evidence，现有 executor fallback 会记录失败的 `web_search` 和成功的 `mock_search` fallback。

## 发布说明

这是一次依赖迁移，不改变 CLI 用户界面。用户拉取变更后需要重新安装依赖，确保环境中有 `ddgs`。
