# 产品路线图（中文）

这份文档是 `docs/roadmap.md` 的中文镜像，方便中文使用者快速理解项目当前完成度与后续边界。

## 当前产品路径

InsightGraph 当前唯一面向正式研究场景的产品路径是 `live-research`。

离线模式继续作为测试、CI 与本地结构验证的 deterministic fallback。联网搜索、LLM、数据库、外部 embedding、完整 trace payload 与 live benchmark 都保持显式 opt-in。

核心优化目标仍然是：**生成高质量、可验证、证据驱动的深度研究报告**。

## 已完成的优化批次

### A. Report Quality v3 - complete

- 强化 deterministic 与 LLM Reporter 的章节级结构约束
- 增加 claim density、evidence density、citation support、unsupported claim 等质量指标
- Critic 输出更具体的 missing source type / section / entity / unsupported claim 提示
- 补齐 deterministic completeness gate

### B. Live Benchmark Case Profiles - complete

- 建立 AI coding agents、上市公司分析、SEC 风险分析、技术趋势分析等 live benchmark case
- 扩展 URL validation、citation precision proxy、source diversity、section coverage、runtime、token、LLM/tool 调用等指标
- 文档化 benchmark 工件边界，避免提交 live 生成结果

### C. Production RAG Hardening - complete

- 文档引用保留 page / section heading / chunk index / snippet offset
- 跨文档检索优先高权威、精确章节、近时效、实体命中
- pgvector 文档检索保持显式 opt-in，本地 JSON 索引仍为默认路径

### D. Memory Quality Loop - complete

- memory writeback 覆盖摘要、实体、已支持结论、引用、来源可靠性、过期元数据
- memory retrieval 按领域、实体、embedding 配置、时效与支持状态过滤
- memory on/off eval proof 已补齐

### E. Dashboard Productization - complete

- Dashboard 展示 section coverage、citation support、source diversity、unsupported claims、URL validation、token、runtime
- evidence drilldown 展示 title、URL、source type、fetch status、citation support status、section ID、snippet
- job stream/event filtering 支持 stage、type、trace ID

### F. API And Operations Hardening - complete

- terminal job retention 与 cleanup 策略落地
- restart/resume smoke path 覆盖 queued jobs、expired running jobs、checkpoint、worker claim
- deployment 文档对齐 API key、SQLite、PostgreSQL、pgvector、trace redaction、benchmark cost

## 仍需显式决策的事项

这些事项会扩大 API 面、攻击面或发布风险，默认不启用：

1. `/tasks` API compatibility aliases
2. MCP runtime invocation behind allowlist
3. release/deploy automation dry-run only
4. Real sandboxed Python/code execution
5. 更进一步的 V3 深度研究循环

## 使用建议

- 如果目标是当前可运行、可演示、可生成研究报告，项目已经完工
- 如果目标是继续提升“更长、更深、更像人工研究员”的报告质量，应从 `docs/roadmap.md` 中剩余的显式决策项继续推进
