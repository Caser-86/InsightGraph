# InsightGraph 演示版故障排查

## 无法访问 Dashboard

1. 检查服务状态：`docker compose ps`
2. 查看日志：`docker compose logs insightgraph`
3. 确认端口未被占用：`netstat -tlnp | grep 8000`
4. 检查防火墙是否放行端口 8000

## 任务未找到 (404)

- 任务 ID 不存在或已被保留策略删除
- 检查 SQLite 文件：`ls -la data/research_jobs.db`
- 如果 DB 文件丢失，检查 volume 挂载是否正确

## LLM 调用失败

1. 确认 API key 正确：检查 `.env` 中 `INSIGHT_GRAPH_LLM_API_KEY`
2. 确认 base URL 可达：
   ```bash
   curl -s https://api.deepseek.com/v1/models -H "Authorization: Bearer $INSIGHT_GRAPH_LLM_API_KEY"
   ```
3. 运行 LLM 连通性检查：
   ```bash
   python scripts/check_llm_provider.py
   ```
4. 检查模型名是否与 provider 兼容（如 DeepSeek 的 chat/reasoner 系列）

## SerpAPI 配额耗尽

1. Dashboard 查看搜索配额快照
2. 对话状态下关闭 SerpAPI：
   - 在 Dashboard 搜索设置中取消勾选 SerpAPI
   - 或在 `.env` 中将 `INSIGHT_GRAPH_SEARCH_PROVIDER` 改为 `duckduckgo`
3. 每日配额次日 0:00 UTC 重置

## 报告内容过短

1. 检查任务详情中的质量诊断面板
2. 可能原因：
   - evidence_count 不足（提高 `INSIGHT_GRAPH_MIN_SUCCESS_EVIDENCE`）
   - LLM 输出被截断（增大 `INSIGHT_GRAPH_LLM_MAX_OUTPUT_TOKENS`）
   - 搜索返回太少结果（考虑开启 SerpAPI 或提高 search_limit）
3. 提高报告强度到 `deep` 或 `deep-plus`

## SQLite 被锁

1. 检查是否有多个 Python 进程在读写同一个 DB：
   ```bash
   ps aux | grep python | grep insight
   ```
2. 停止所有进程后重新启动
3. 如果 journal 残留导致问题：
   ```bash
   rm data/research_jobs.db-journal
   docker compose restart insightgraph
   ```

## WebSocket 断开

1. 确认 Nginx 配置包含 WebSocket upgrade header：
   ```
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection "upgrade";
   ```
2. 检查网络是否稳定
3. Dashboard 会自动回退到轮询模式

## 服务重启后任务丢失

1. 确认 `.env` 中：
   ```
   INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite
   INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/data/research_jobs.db
   ```
2. 确认 `/data` volume 已正确挂载
3. 运行中的任务会自动标记为 failed 并可在 restart 后重新排队

## 常用诊断命令

```bash
# 查看最近任务
curl -s http://localhost:8000/research/jobs?limit=5

# 查看单个任务详情
curl -s http://localhost:8000/research/jobs/<job-id>

# 运行演示环境检查
python scripts/validate_demo_env.py

# 检查 LLM 连通性
python scripts/check_llm_provider.py

# 检查搜索提供商
python scripts/check_search_provider.py --provider duckduckgo
python scripts/check_search_provider.py --provider serpapi
```
