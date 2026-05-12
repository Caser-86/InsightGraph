# InsightGraph Benchmarks

This document summarizes how to measure InsightGraph performance and report
quality without confusing deterministic offline checks with live networked
evaluation.

## Benchmark Modes

| Mode | Use case | Cost | Network |
| --- | --- | --- | --- |
| Offline | local validation, CI, deterministic regression checks | none | no |
| Live | real-world evaluation before demos or delivery | controlled | yes |
| Smoke | deployment health and basic operability | low | local or deployed target |

## Offline Benchmark

```bash
python scripts/benchmark_research.py
python scripts/benchmark_research.py --markdown
```

Properties:

- deterministic
- no public network access
- no live LLM dependency
- suitable for regression checks

## Live Benchmark

```bash
python scripts/benchmark_live_research.py --allow-live --output reports/live-benchmark.json
python scripts/benchmark_live_research.py --allow-live --output reports/live-benchmark.json --case-file docs/benchmarks/live-research-cases.json
```

Or:

```bash
export INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1
python scripts/benchmark_live_research.py --output reports/live-benchmark.json
```

Notes:

- always uses `live-research`
- may incur network/LLM cost
- should remain manual opt-in
- do not commit generated live benchmark reports

## Benchmark Metrics

Typical live benchmark output includes:

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

## Deployment Smoke

```bash
insight-graph-smoke http://127.0.0.1:8000
insight-graph-smoke http://127.0.0.1:8000 --api-key "$INSIGHT_GRAPH_API_KEY" --markdown
```

Smoke checks cover:

- `/health`
- `/dashboard`
- `/research/jobs/summary`

## Capacity Guidance

The project is optimized first for correctness, transparency, and safe runtime
control rather than raw parallel throughput. For production-like demos:

- prefer SQLite job storage
- use startup worker claim for restart recovery
- keep live benchmark manual
- scale concurrency only after report-quality stability is proven
