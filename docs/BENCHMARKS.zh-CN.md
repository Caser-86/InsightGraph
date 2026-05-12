# 基准测试说明

## 模式

- Offline：本地验证、CI、回归检查
- Live：真实搜索与 LLM 条件下的效果验证
- Smoke：部署健康检查

## 离线 Benchmark

```bash
python scripts/benchmark_research.py
python scripts/benchmark_research.py --markdown
```

## Live Benchmark

```bash
python scripts/benchmark_live_research.py --allow-live --output reports/live-benchmark.json
```

或：

```bash
export INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1
python scripts/benchmark_live_research.py --output reports/live-benchmark.json
```

注意：

- 始终走 `live-research`
- 可能产生 network/LLM cost
- 不要提交生成的 live benchmark 报告
