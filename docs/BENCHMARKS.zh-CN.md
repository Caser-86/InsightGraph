# InsightGraph 基准测试说明

这份文档解释如何衡量 InsightGraph 的性能与报告质量，并区分离线校验与 live 评测。

## 基准模式

| 模式 | 适用场景 | 成本 | 是否联网 |
| --- | --- | --- | --- |
| Offline | 本地验证、CI、回归测试 | 无 | 否 |
| Live | 演示前真实验证 | 可控 | 是 |
| Smoke | 部署后健康检查 | 低 | 本地或目标环境 |

## 离线 Benchmark

```bash
python scripts/benchmark_research.py
python scripts/benchmark_research.py --markdown
```

特点：

- deterministic
- 不访问公网
- 不依赖 live LLM
- 适合回归验证

## Live Benchmark

```bash
python scripts/benchmark_live_research.py --allow-live --output reports/live-benchmark.json
python scripts/benchmark_live_research.py --allow-live --output reports/live-benchmark.json --case-file docs/benchmarks/live-research-cases.json
```

或：

```bash
export INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1
python scripts/benchmark_live_research.py --output reports/live-benchmark.json
```

说明：

- 固定走 `live-research`
- 可能产生 `network/LLM cost`
- 建议保持手动 opt-in
- 不要提交 live benchmark 生成报告

## 常见指标

- `url_validation_rate`
- `citation_precision_proxy`
- `source_diversity_by_type`
- `source_diversity_by_domain`
- `section_coverage`
- `report_depth_words`
- `runtime_ms`
- `llm_call_count`
- `tool_call_count`
- `total_tokens`

## 部署冒烟

```bash
insight-graph-smoke http://127.0.0.1:8000
insight-graph-smoke http://127.0.0.1:8000 --api-key "$INSIGHT_GRAPH_API_KEY" --markdown
```

检查内容：

- `/health`
- `/dashboard`
- `/research/jobs/summary`
