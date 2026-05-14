# 常见问题（FAQ）

## 安装与环境

### Q: InsightGraph 需要 API Key 吗？

不一定。

- 离线模式不需要
- `live-research` 通常需要搜索或 LLM 配置
- Dashboard 和 API 是否需要鉴权，取决于是否设置了 `INSIGHT_GRAPH_API_KEY`

### Q: 支持哪些 LLM？

任何 OpenAI-compatible endpoint 都可以，包括：

- DeepSeek
- OpenAI
- Azure OpenAI-compatible 代理
- 本地 Ollama / LM Studio / vLLM / 其他兼容网关

### Q: 支持哪些搜索方式？

当前支持：

- `mock`
- `duckduckgo`
- `google`
- `serpapi`

其中 `mock` 是默认离线路径。

## 使用方式

### Q: 离线模式和 `live-research` 有什么区别？

离线模式：

- 不访问公网
- 不调用 LLM
- 适合测试、CI、结构验证

`live-research`：

- 启用联网搜索
- 启用 LLM Analyst / Reporter
- 启用 GitHub / SEC / URL validation 等相关能力
- 可能产生 network/LLM cost

### Q: 如何快速试运行？

```bash
insight-graph research "Compare Cursor, OpenCode, and GitHub Copilot"
```

或：

```bash
insight-graph research --preset live-research "Compare Cursor, OpenCode, and GitHub Copilot"
```

### Q: 如何启动 API 和 Dashboard？

Windows 本地测试建议使用稳定启动脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_dashboard.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\dashboard_status.ps1
```

打开 `dashboard_status.ps1` 输出的地址，例如：

- `http://127.0.0.1:8003/health`
- `http://127.0.0.1:8003/docs`
- `http://127.0.0.1:8003/dashboard`

停止服务：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop_dashboard.ps1
```

## 异步任务

### Q: 同步 `/research` 和异步 `/research/jobs` 怎么选？

建议：

- 小查询、开发调试：`/research`
- 长查询、演示、Dashboard：`/research/jobs`

### Q: 现在取消任务的语义是什么？

当前规则：

- `queued` 可以取消
- `running` 也可以取消
- `succeeded` / `failed` / `cancelled` 不能取消

终态任务再次取消会返回 `409`。

### Q: 重启后任务会怎样？

取决于存储方式：

- JSON 元数据：未完成任务会被标记为失败
- SQLite：排队任务会保留，过期运行中任务会重新进入可 claim 状态
- 若同时开启 `INSIGHT_GRAPH_CHECKPOINT_RESUME=1`，任务可从最新 checkpoint 继续

## Memory 与持久化

### Q: Memory 是默认开启的吗？

不是。

默认是进程内 memory。要做长期记忆，一般需要：

- `INSIGHT_GRAPH_MEMORY_BACKEND=pgvector`
- `INSIGHT_GRAPH_USE_MEMORY_CONTEXT=1`

### Q: 报告会自动写回 memory 吗？

只有在显式开启时：

```bash
export INSIGHT_GRAPH_MEMORY_WRITEBACK=1
```

成功报告会写回摘要、实体、已支持结论、引用和来源可靠性记录。

## 成本与安全

### Q: live benchmark 会不会花钱？

会，可能产生 network/LLM cost。

因此它保持手动 opt-in：

- `scripts/benchmark_live_research.py --allow-live`
- 或 `INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1`

并且不要提交生成出来的 live benchmark 报告。

### Q: 项目有没有真正的沙箱代码执行？

没有。

真实 sandboxed Python/code execution 仍是 deferred item，不属于默认能力。

### Q: MCP runtime 调用已经开放了吗？

没有。

当前仍是 deferred item，不是默认可用功能。

## 文档建议阅读顺序

1. `README.md`
2. `docs/README.zh-CN.md`
3. `docs/QUICK_START.md`
4. `docs/research-jobs-api.zh-CN.md`
5. `docs/configuration.zh-CN.md`
6. `docs/deployment.zh-CN.md`
