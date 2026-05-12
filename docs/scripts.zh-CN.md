# 脚本说明

## 常用脚本

| 脚本 | 用途 |
|------|------|
| `scripts/run_research.py` | 运行一次研究任务，输出 Markdown 或 JSON |
| `scripts/run_with_llm_log.py` | 运行任务并输出安全 LLM 元数据日志 |
| `scripts/validate_sources.py` | 离线验证引用与 References |
| `scripts/benchmark_research.py` | 离线 benchmark |
| `scripts/benchmark_live_research.py` | 手动 opt-in live benchmark |
| `scripts/validate_document_reader.py` | 验证本地文档读取 |
| `scripts/validate_pdf_fetch.py` | 验证 PDF 抓取与检索 |
| `insight-graph-smoke` | API / Dashboard 部署 smoke |

## 示例

```bash
python scripts/run_research.py "Analyze Xiaomi EV strategy"
python scripts/run_with_llm_log.py "Analyze Xiaomi EV strategy"
python scripts/benchmark_research.py --markdown
python scripts/validate_sources.py report.md --markdown
```
