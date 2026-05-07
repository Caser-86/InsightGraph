# InsightGraph Performance Benchmarks

本文档描述 InsightGraph 的性能基准、优化指南和成本估算。

## 基准测试框架

InsightGraph 提供三种基准测试方式：

| 模式 | 适用场景 | 成本 | 网络访问 |
|-----|---------|------|---------|
| **离线** | 本地测试、CI/CD、功能验证 | 无 | ❌ |
| **Live** | 真实性能测试、上线前验证 | 有 | ✅ |
| **Benchmark** | 持续性能监控、回归检测 | 可控 | 可选 |

## 离线性能基准

### 执行离线基准测试

```bash
python scripts/benchmark_research.py \
  --case-file docs/benchmarks/live-research-cases.json \
  --output reports/offline-benchmark.json
```

### 典型离线性能指标（单次研究）

| 指标 | 值 | 说明 |
|------|-----|------|
| **端到端耗时** | 2-5s | Planner → Collector → Analyst → Reporter |
| **Planner** | ~200ms | 规划和任务分解 |
| **Collector** | ~1.5s | Mock 搜索和证据采集 |
| **Analyst** | ~800ms | 分析（无 LLM，用规则） |
| **Critic** | ~200ms | 证据评价 |
| **Reporter** | ~800ms | 报告生成（无 LLM，用模板） |
| **内存占用** | 50-100MB | Python 进程基线 |
| **吞吐量** | ~12 req/min | 单进程串行处理 |

### 缓存和优化

离线模式使用内存缓存：

```bash
# 第一次运行（冷启动）
$ time python -m insight_graph.cli research "Query 1"
real    0m4.234s

# 第二次运行（热缓存）
$ time python -m insight_graph.cli research "Query 1"
real    0m0.982s
```

缓存命中减少 ~75% 的执行时间。

## 实时性能基准

### 启用实时基准测试

实时基准需要显式授权和环保成本：

```bash
# 要求显式环境变量或 CLI 选项
export INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1

python scripts/benchmark_live_research.py \
  --allow-live \
  --case-file docs/benchmarks/live-research-cases.json \
  --output reports/live-benchmark.json
```

**警告**: 实时基准会产生 API 调用费用。每个研究约 $0.10-0.50（取决于 provider 和模型）。

### 典型实时性能指标

假设使用 DuckDuckGo（免费）+ DeepSeek-R1（付费）：

| 阶段 | 耗时 | 说明 |
|-----|------|------|
| **Planner** | 1-2s | LLM 规划调用 |
| **Web Search** | 2-3s | DuckDuckGo API 延迟 |
| **URL Fetch** (×5) | 8-12s | 网络延迟（并行） |
| **Analyst** | 5-10s | LLM 长上下文分析 |
| **Reporter** | 3-8s | LLM 报告生成 |
| **Total** | 20-40s | 端到端（平均） |

### 端到端示例

```bash
time insight-graph research \
  --preset live-research \
  "Compare Cursor and GitHub Copilot"

# Typical output:
# [Planner] Planning... 1.23s
# [Collector] Searching web... 2.45s
# [Collector] Fetching URLs (5)... 9.87s
# [Analyst] Analyzing... 7.23s
# [Critic] Evaluating... 1.02s
# [Reporter] Generating report... 5.43s
# Total: 27.23s
```

## 成本分析

### 成本因子

| Provider | 成本 | 免费额度 | 备注 |
|---------|------|---------|------|
| **DuckDuckGo** | 免费 | 无限 | 推荐免费选项 |
| **SerpAPI** | $10/mo 100 calls | 100 calls | 按额度计费 |
| **Google API** | 已关闭 | N/A | 2026 年停止服务 |
| **OpenAI** | $0.01-0.10/req | 无 | 依模型而定 |
| **DeepSeek** | $0.14-0.55/M tokens | 无 | 快速+推理模型 |
| **Anthropic** | $0.03-0.30/M tokens | 无 | Claude 系列 |

### 典型成本估算（单次研究）

使用 DuckDuckGo + DeepSeek-R1：

```
成本 = 搜索费用 + 分析费用 + 报告费用

搜索: DuckDuckGo 免费
分析: ~3000 tokens × $0.14/M tokens = $0.00042
报告: ~2000 tokens × $0.28/M tokens = $0.00056
─────────────────────────────────────
总计: ~$0.001 / 研究 = 少于 0.1¢
```

### 月度成本估算

假设每天 50 次研究，每次 $0.01（使用便宜模型）：

```
日成本: 50 × $0.01 = $0.50
月成本: $0.50 × 30 = $15
年成本: $15 × 12 = $180
```

使用本地 LLM（Ollama）可将成本降至 **$0**。

## 可扩展性基准

### 单机（UV icorn）吞吐量

```bash
# 启动 API
uvicorn insight_graph.api:app --host 127.0.0.1 --port 8000

# 并发测试（使用 wrk 或 Apache Bench）
wrk -t 4 -c 50 -d 30s \
  -s benchmark.lua \
  http://127.0.0.1:8000/research
```

**预期结果**（离线模式，单进程）：

| 并发数 | 吞吐量 | 平均响应时间 | P99 |
|--------|---------|-------------|-----|
| 1 | 12 req/min | 5s | 6s |
| 5 | 25 req/min | 12s | 20s |
| 10 | 30 req/min | 20s | 40s |
| 50 | 32 req/min | 100s | 180s |

**瓶颈**: 单进程串行执行。研究不是 CPU 密集，而是 I/O 密集（网络、LLM API）。

### 多进程扩展

使用 Gunicorn 或 Kubernetes HPA：

```bash
# Gunicorn with 4 workers
gunicorn \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 \
  insight_graph.api:app
```

**预期改进**：

- **吞吐量**: 4-5x 提升（与 worker 数量成线性关系）
- **响应时间**: 相同（P50 未改变，但队列延迟减少）
- **内存**: 每个 worker ~100MB，4 workers = 400MB + 共享库

### Kubernetes 自动扩展

在 `k8s/insightgraph-deployment.yaml` 中配置 HPA：

```yaml
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**预期行为**：

- CPU 利用率 > 70% 时自动扩展
- 最多 10 个副本，线性扩展到 300+ req/min（实际 I/O 受限）

## 资源占用基准

### 内存占用

```bash
# 启动 API，测量内存
$ python -c "
import psutil
import resource
from insight_graph.api import app

p = psutil.Process()
print(f'RSS: {p.memory_info().rss / 1024 / 1024:.1f} MB')
print(f'VMS: {p.memory_info().vms / 1024 / 1024:.1f} MB')
"

# 典型输出:
# RSS: 87.3 MB  (实际占用)
# VMS: 256.7 MB (虚拟地址空间)
```

**峰值内存**（处理大型研究）：

| 场景 | 内存 | 说明 |
|------|------|------|
| 启动 | 50MB | 导入库 |
| 热待命 | 80MB | 缓存和连接池 |
| 处理研究 | 150-200MB | 证据存储 + LLM 上下文 |
| 大文档处理 | 300-400MB | PDF 或大 HTML |

### CPU 占用

CPU 使用通常很低（I/O 受限）：

```bash
# 监控 CPU
$ watch -n 1 'ps aux | grep uvicorn'

# 离线研究: 1-3% CPU（大多数时间等待 I/O）
# 实时研究: 2-5% CPU（LLM 处理和网络延迟）
```

### 磁盘占用

```bash
# SQLite 数据库增长
$ du -sh jobs.sqlite3

# 典型增长: 每个研究 ~50KB（元数据）
# 1000 个研究 = ~50MB
# 10,000 个研究 = ~500MB
```

## 优化指南

### 查询优化

#### 减少搜索结果

```bash
export INSIGHT_GRAPH_SEARCH_LIMIT=3      # 从 20 减到 3
export INSIGHT_GRAPH_MAX_FETCHES=10      # 限制 URL fetch 数
export INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS=2  # 限制采集轮次
```

**效果**: 减少 40-60% 的执行时间和网络成本

#### 禁用 URL 验证

```bash
export INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=0
```

**效果**: 省去 2-5s 的 URL 验证时间

#### 使用更便宜的 LLM

```bash
# 使用快速模型分析
export INSIGHT_GRAPH_LLM_MODEL=gpt-3.5-turbo
```

**效果**: 成本减少 50-80%（质量权衡）

### 系统优化

#### 启用缓存

```bash
export INSIGHT_GRAPH_CACHE_BACKEND=redis
export INSIGHT_GRAPH_REDIS_URL=redis://localhost:6379
```

**效果**: 重复查询快 90%

#### 启用对话压缩

```bash
export INSIGHT_GRAPH_CONVERSATION_COMPRESSION=1
```

**效果**: 减少 30-50% 的 LLM token 使用

#### 使用本地 LLM

```bash
# 启动 Ollama
ollama run deepseek-r1:7b

# 配置 InsightGraph
export INSIGHT_GRAPH_LLM_BASE_URL=http://localhost:11434/v1
export INSIGHT_GRAPH_LLM_MODEL=deepseek-r1:7b
```

**效果**: 成本降至 $0，延迟取决于 GPU（通常 10-30s）

## 性能回归检测

### 持续基准测试

在 CI 中运行定期基准测试：

```bash
# 每周运行一次
0 0 * * 0 cd /opt/insightgraph && python scripts/benchmark_research.py --output reports/baseline-$(date +\%Y\%m\%d).json
```

### 对比和告警

```bash
# 比较两个基准运行
python scripts/compare_benchmarks.py reports/baseline-20260507.json reports/baseline-20260514.json

# 输出:
# Metric                    | Baseline | Latest | Change
# ──────────────────────────┼──────────┼────────┼─────────
# End-to-End (ms)           | 4234     | 4521   | +6.8% ⚠️
# Planner (ms)              | 198      | 203    | +2.5% ✓
# Collector (ms)            | 1523     | 1634   | +7.3% ⚠️
# ...
```

告警阈值（触发调查）：

- 端到端 > ±10% 变化
- 内存 > ±15% 变化
- 吞吐量 < 80% 基线

## 故障排查

### 性能下降诊断

| 症状 | 原因 | 解决 |
|------|------|------|
| 响应时间突然增加 | 网络延迟、API 限流 | 检查网络、增加重试 |
| 内存不断增长 | 内存泄漏、缓存未清理 | 重启进程、检查日志 |
| CPU 突然高涨 | 锁竞争、大量并发 | 增加 worker 数量 |
| 搜索结果为空 | Provider 故障、限流 | 切换 provider、减少频率 |
| LLM 调用失败 | API 限流、认证问题 | 检查 key、增加重试延迟 |

### 性能监控

使用 Prometheus + Grafana：

```yaml
# 关键指标
- insight_graph_research_duration_seconds
- insight_graph_llm_call_duration_seconds
- insight_graph_search_success_rate
- insight_graph_evidence_count
- insight_graph_memory_bytes
```

## 基准测试用例

默认测试用例位于 `docs/benchmarks/live-research-cases.json`：

```json
[
  {
    "id": "benchmark-001",
    "query": "Compare Cursor, OpenCode, and GitHub Copilot",
    "category": "product-comparison",
    "expected_sections": ["Overview", "Features", "Pricing", "Pros/Cons"]
  },
  {
    "id": "benchmark-002",
    "query": "Technical trends in AI coding agents 2025",
    "category": "market-analysis",
    "expected_sections": ["Executive Summary", "Key Trends", "Market Size"]
  }
]
```

## 报告生成

生成可视化基准报告：

```bash
python scripts/benchmark_research.py \
  --case-file docs/benchmarks/live-research-cases.json \
  --output reports/benchmark.json \
  --markdown \
  --output-md reports/benchmark.md
```

输出包括：

- 执行时间分布图
- 内存占用趋势
- 成本分析
- Top 10 最慢的查询

## 参考文献

- [LangGraph 性能优化](https://langchain-ai.github.io/langgraph/)
- [FastAPI 部署最佳实践](https://fastapi.tiangolo.com/deployment/)
- [Kubernetes HPA 文档](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
